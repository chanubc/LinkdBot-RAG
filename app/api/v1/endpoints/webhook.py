import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies import get_link_service, get_telegram_client, get_user_repository
from app.api.v1.controllers.telegram_controller import (
    COMMANDS,
    HandlerCtx,
    handle_callback,
    handle_text,
    handle_url,
)
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.services.link_service import LinkService

logger = logging.getLogger(__name__)
router = APIRouter()


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

    # 1. callback_query (인라인 버튼)
    if callback := data.get("callback_query"):
        await handle_callback(callback, telegram)
        return {"ok": True}

    # 2. message 추출
    message = data.get("message") or data.get("channel_post")
    if not message:
        return {"ok": True}

    text: str = message.get("text", "")
    telegram_id: int = message["from"]["id"]
    logger.info("Received message from %s: %s", telegram_id, text)

    ctx = HandlerCtx(
        telegram_id=telegram_id,
        text=text,
        message=message,
        background_tasks=background_tasks,
        link_service=link_service,
        telegram=telegram,
        user_repo=user_repo,
    )

    # 3. Command Router dispatch
    for prefix, handler in COMMANDS.items():
        if text.startswith(prefix):
            await handler(ctx)
            return {"ok": True}

    # 4. URL fallback
    urls, memo = link_service.extract_urls(text)
    if urls:
        await handle_url(ctx, urls, memo)
        return {"ok": True}

    # 5. 일반 텍스트 → 검색 fallback
    await handle_text(ctx)
    return {"ok": True}
