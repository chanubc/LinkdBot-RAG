import re

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies import get_link_service, get_telegram_client
from app.infrastructure.external.telegram_client import TelegramClient
from app.services.link_service import LinkService

router = APIRouter()

_URL_RE = re.compile(r"https?://\S+")


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    link_service: LinkService = Depends(get_link_service),
    telegram: TelegramClient = Depends(get_telegram_client),
):
    """텔레그램 웹훅 수신 엔드포인트."""
    data = await request.json()
    message = data.get("message") or data.get("channel_post")
    if not message:
        return {"ok": True}

    text: str = message.get("text", "")
    telegram_id: int = message["from"]["id"]

    if text.startswith("/start"):
        await telegram.send_notion_connect_button(telegram_id, telegram_id)
        return {"ok": True}

    for url in _URL_RE.findall(text):
        background_tasks.add_task(link_service.process_link, telegram_id, url)

    return {"ok": True}
