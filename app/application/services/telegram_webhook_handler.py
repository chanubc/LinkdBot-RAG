from fastapi import BackgroundTasks

from app.application.services.message_router_service import MessageRouterService
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.mark_read_usecase import MarkReadUseCase
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import extract_urls

from app.core.logger import logger


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
        mark_read_uc: MarkReadUseCase,
        user_repo: IUserRepository,
    ):
        self._message_router = message_router
        self._telegram = telegram
        self._save_link_uc = save_link_uc
        self._mark_read_uc = mark_read_uc
        self._user_repo = user_repo

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
        first_name = from_user.get("first_name")
        if telegram_id is None:
            logger.warning(f"Cannot determine telegram_id from message: {message}")
            return
        logger.info(f"Received message from {telegram_id}: {text}")

        # Ensure user exists and update first_name if available
        await self._user_repo.ensure_exists(telegram_id, first_name)

        # URL 검출 → LinkRepository 저장 (별도 처리)
        urls, memo = extract_urls(text)
        if urls:
            for url in urls:
                logger.info(f"Processing URL from {telegram_id}: {url}")
                # Background task로 SaveLinkUseCase 실행
                # SaveLinkUseCase 내부에서 "저장 중", "완료/실패" 메시지 관리
                # 웹훅은 즉시 응답 (< 100ms)
                background_tasks.add_task(self._save_link_uc.execute, telegram_id, url, memo)
            return

        # 메시지(슬래쉬 명령어 + 일반 텍스트) → MessageRouter로 위임 (백그라운드)
        # (OpenAI, Notion I/O 대기로 인한 웹훅 타임아웃 방지)
        background_tasks.add_task(self._message_router.route, telegram_id, text)

    async def _handle_callback(self, callback: dict) -> None:
        """콜백 쿼리 처리 (도움말 버튼, 읽음 처리 버튼 등)."""
        await self._telegram.answer_callback_query(callback["id"])
        data = callback.get("data", "")
        chat_id: int | None = (callback.get("from") or {}).get("id")
        if not chat_id:
            return

        if data == "help":
            await self._telegram.send_help_message(chat_id)
        elif data.startswith("mark_read:"):
            try:
                link_id = int(data.split(":", 1)[1])
                success = await self._mark_read_uc.execute(chat_id, link_id)
                if success:
                    await self._telegram.send_message(chat_id, "✅ 읽음 처리되었습니다.")
                else:
                    await self._telegram.send_message(chat_id, "링크를 찾을 수 없습니다.")
            except Exception as exc:
                logger.warning(f"mark_read callback failed: {exc}")
