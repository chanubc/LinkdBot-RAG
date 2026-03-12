from fastapi import BackgroundTasks

from app.application.ports.telegram_port import TelegramPort
from app.application.services.message_router_service import MessageRouterService
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
        if callback := data.get("callback_query"):
            await self._handle_callback(callback)
            return

        message = data.get("message") or data.get("channel_post")
        if not message:
            return

        text: str = message.get("text", "")
        from_user = message.get("from") or {}
        telegram_id = from_user.get("id") or message.get("chat", {}).get("id")
        first_name = from_user.get("first_name")
        if telegram_id is None:
            logger.warning(f"Cannot determine telegram_id from message: {message}")
            return
        logger.info(f"Received message from {telegram_id}: {text}")

        await self._user_repo.ensure_exists(telegram_id, first_name)

        urls, memo = extract_urls(text)
        if urls:
            for url in urls:
                logger.info(f"Processing URL from {telegram_id}: {url}")
                background_tasks.add_task(self._save_link_uc.execute, telegram_id, url, memo)
            return

        background_tasks.add_task(self._message_router.route, telegram_id, text)

    async def _handle_callback(self, callback: dict) -> None:
        await self._telegram.answer_callback_query(callback["id"])
        data = callback.get("data", "")
        chat_id: int | None = (callback.get("from") or {}).get("id")
        if not chat_id:
            return

        if data in {"help", "menu:help"}:
            await self._telegram.send_help_message(chat_id)
        elif data == "menu:save":
            await self._telegram.send_message(
                chat_id,
                "🔗 저장할 URL을 채팅에 그대로 보내주세요. 메모를 함께 적으면 같이 저장돼요.\n"
                "예시: <code>https://example.com 이 글은 나중에 다시 보기</code>",
            )
        elif data == "menu:search":
            await self._telegram.send_message(
                chat_id,
                "🔍 <code>/search [검색어]</code> 로 저장된 링크를 찾을 수 있어요.\n"
                "예시: <code>/search RAG 아키텍처</code>",
            )
        elif data == "menu:ask":
            await self._telegram.send_message(
                chat_id,
                "🤖 <code>/ask [질문]</code> 으로 저장된 지식을 바탕으로 답변해드려요.\n"
                "예시: <code>/ask 내가 저장한 RAG 관련 내용 요약해줘</code>",
            )
        elif data == "menu:report":
            await self._message_router.route(chat_id, "/report")
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
