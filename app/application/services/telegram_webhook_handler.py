import logging

from fastapi import BackgroundTasks

from app.application.services.message_router_service import MessageRouterService
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.utils.text import extract_urls

logger = logging.getLogger(__name__)


class TelegramWebhookHandler:
    """
    책임: Telegram 웹훅 수신 + callback 처리 + URL 검출만
    (메시지 라우팅은 MessageRouterService에 위임)
    """

    def __init__(
        self,
        message_router: MessageRouterService,
        telegram: TelegramPort,
        save_link_uc: SaveLinkUseCase,
    ):
        self._message_router = message_router
        self._telegram = telegram
        self._save_link_uc = save_link_uc

    async def handle(self, data: dict, background_tasks: BackgroundTasks) -> None:
        """웹훅 수신 후 callback/URL/message로 분기."""

        # callback_query 처리
        if callback := data.get("callback_query"):
            await self._handle_callback(callback)
            return

        # message 파싱
        message = data.get("message") or data.get("channel_post")
        if not message:
            return

        text: str = message.get("text", "")
        telegram_id: int = message["from"]["id"]
        logger.info("Received message from %s: %s", telegram_id, text)

        # URL 검출 → LinkRepository 저장 (별도 처리)
        urls, memo = extract_urls(text)
        if urls:
            for url in urls:
                logger.info("Processing URL from %s: %s", telegram_id, url)
                await self._telegram.send_message(telegram_id, "🔍 링크를 저장하는 중입니다...")
                background_tasks.add_task(self._save_link_uc.execute, telegram_id, url, memo)
            return

        # 메시지(슬래쉬 명령어 + 일반 텍스트) → MessageRouter로 위임
        await self._message_router.route(telegram_id, text)

    async def _handle_callback(self, callback: dict) -> None:
        """콜백 쿼리 처리 (도움말 버튼 등)."""
        await self._telegram.answer_callback_query(callback["id"])
        if callback.get("data") == "help":
            chat_id: int | None = (callback.get("from") or {}).get("id")
            if chat_id:
                await self._telegram.send_help_message(chat_id)
