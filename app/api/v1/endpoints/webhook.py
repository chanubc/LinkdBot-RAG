import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.api.dependencies import get_webhook_service
from app.application.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    webhook_service: WebhookService = Depends(get_webhook_service),
):
    """텔레그램 웹훅 수신 엔드포인트."""
    data = await request.json()
    await webhook_service.handle(data, background_tasks)
    return {"ok": True}
