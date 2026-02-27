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
        # channel_post는 "from" 필드 부재 가능 → chat.id로 폴백
        from_user = message.get("from") or {}
        telegram_id = from_user.get("id") or message.get("chat", {}).get("id")
        if telegram_id is None:
            logger.warning("Cannot determine telegram_id from message: %s", message)
            return
        logger.info("Received message from %s: %s", telegram_id, text)

        # URL 검출 → LinkRepository 저장 (별도 처리)
        urls, memo = extract_urls(text)
        if urls:
            for url in urls:
                logger.info("Processing URL from %s: %s", telegram_id, url)
                # Background task로 SaveLinkUseCase 실행
                # SaveLinkUseCase 내부에서 "저장 중", "완료/실패" 메시지 관리
                # 웹훅은 즉시 응답 (< 100ms)
                background_tasks.add_task(self._save_link_uc.execute, telegram_id, url, memo)
            return

        # 메시지(슬래쉬 명령어 + 일반 텍스트) → MessageRouter로 위임 (백그라운드)
        # (OpenAI, Notion I/O 대기로 인한 웹훅 타임아웃 방지)
        background_tasks.add_task(self._message_router.route, telegram_id, text, background_tasks)

    async def _handle_callback(self, callback: dict) -> None:
        """콜백 쿼리 처리 (도움말 버튼 등)."""
        await self._telegram.answer_callback_query(callback["id"])
        if callback.get("data") == "help":
            chat_id: int | None = (callback.get("from") or {}).get("id")
            if chat_id:
                await self._telegram.send_help_message(chat_id)
