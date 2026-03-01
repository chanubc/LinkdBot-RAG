from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies.webhook_di import get_webhook_handler
from app.application.services.telegram_webhook_handler import TelegramWebhookHandler

router = APIRouter()


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    handler: TelegramWebhookHandler = Depends(get_webhook_handler),
):
    """텔레그램 웹훅 수신 엔드포인트."""
    data = await request.json()
    await handler.handle(data, background_tasks)
    return {"ok": True}
