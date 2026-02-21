import logging
import re

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies import get_link_service, get_telegram_client, get_user_repository
from app.config import settings
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.infrastructure.state_store import create as create_state_token
from app.services.link_service import LinkService

logger = logging.getLogger(__name__)
router = APIRouter()

_URL_RE = re.compile(r"https?://\S+")


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    link_service: LinkService = Depends(get_link_service),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
):
    """텔레그램 웹훅 수신 엔드포인트."""
    data = await request.json()

    if callback := data.get("callback_query"):
        await telegram.answer_callback_query(callback["id"])
        if callback.get("data") == "help":
            chat_id: int | None = (callback.get("from") or {}).get("id")
            if chat_id:
                await telegram.send_help_message(chat_id)
        return {"ok": True}

    message = data.get("message") or data.get("channel_post")
    if not message:
        return {"ok": True}

    text: str = message.get("text", "")
    telegram_id: int = message["from"]["id"]
    logger.info("Received message from %s: %s", telegram_id, text)

    if text.startswith("/start"):
        user = await user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = message.get("from", {}).get("first_name")
            await telegram.send_welcome_connected(telegram_id, first_name)
        else:
            token = create_state_token(telegram_id)
            login_url = (
                settings.NOTION_REDIRECT_URI.replace("/callback", "/login")
                + f"?token={token}"
            )
            await telegram.send_notion_connect_button(telegram_id, login_url)
        return {"ok": True}

    urls = _URL_RE.findall(text)
    if urls:
        memo = _URL_RE.sub("", text).strip() or None
        for url in urls:
            logger.info("Processing URL from %s: %s", telegram_id, url)
            background_tasks.add_task(link_service.process_link, telegram_id, url, memo)
    elif text.strip():
        logger.info("Processing memo from %s", telegram_id)
        background_tasks.add_task(link_service.process_memo, telegram_id, text.strip())

    return {"ok": True}
