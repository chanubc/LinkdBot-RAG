import logging

from fastapi import BackgroundTasks

from app.domain.text import extract_urls
from app.infrastructure.external.telegram_client import TelegramClient
from app.domain.repositories.i_user_repository import IUserRepository
from app.services.auth_service import AuthService
from app.services.link_service import LinkService

logger = logging.getLogger(__name__)


class WebhookService:
    def __init__(
        self,
        link_service: LinkService,
        telegram: TelegramClient,
        user_repo: IUserRepository,
        auth_service: AuthService,
    ) -> None:
        self._link_service = link_service
        self._telegram = telegram
        self._user_repo = user_repo
        self._auth_service = auth_service

    async def handle(self, data: dict, background_tasks: BackgroundTasks) -> None:
        """텔레그램 업데이트 수신 후 타입에 따라 분기."""
        if callback := data.get("callback_query"):
            await self._handle_callback(callback)
            return

        message = data.get("message") or data.get("channel_post")
        if not message:
            return

        text: str = message.get("text", "")
        telegram_id: int = message["from"]["id"]
        logger.info("Received message from %s: %s", telegram_id, text)

        if text.startswith("/start"):
            await self._handle_start(telegram_id, message)
        elif text.startswith("/memo"):
            await self._handle_memo(telegram_id, text, background_tasks)
        elif text.startswith("/search"):
            await self._handle_search(telegram_id, text)
        else:
            urls, memo = extract_urls(text)
            if urls:
                await self._handle_url(telegram_id, urls, memo, background_tasks)
            else:
                await self._handle_text(telegram_id, text)

    # ── Private Handlers ─────────────────────────────────────────────────────

    async def _handle_callback(self, callback: dict) -> None:
        await self._telegram.answer_callback_query(callback["id"])
        if callback.get("data") == "help":
            chat_id: int | None = (callback.get("from") or {}).get("id")
            if chat_id:
                await self._telegram.send_help_message(chat_id)

    async def _handle_start(self, telegram_id: int, message: dict) -> None:
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = message.get("from", {}).get("first_name")
            await self._telegram.send_welcome_connected(telegram_id, first_name)
        else:
            login_url = self._auth_service.create_login_url(telegram_id)
            await self._telegram.send_notion_connect_button(telegram_id, login_url)

    async def _handle_memo(
        self, telegram_id: int, text: str, background_tasks: BackgroundTasks
    ) -> None:
        memo_text = text[5:].strip()
        if memo_text:
            logger.info("Processing memo from %s", telegram_id)
            background_tasks.add_task(
                self._link_service.process_memo, telegram_id, memo_text
            )
        else:
            await self._telegram.send_message(
                telegram_id,
                "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
            )

    async def _handle_search(self, telegram_id: int, text: str) -> None:
        query = text[7:].strip()
        if not query:
            await self._telegram.send_message(
                telegram_id,
                "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
            )
            return
        logger.info("Searching for %s from %s", query, telegram_id)
        results = await self._link_service.search(telegram_id, query)
        await self._telegram.send_search_results(telegram_id, query, results)

    async def _handle_url(
        self,
        telegram_id: int,
        urls: list[str],
        memo: str | None,
        background_tasks: BackgroundTasks,
    ) -> None:
        for url in urls:
            logger.info("Processing URL from %s: %s", telegram_id, url)
            background_tasks.add_task(
                self._link_service.process_link, telegram_id, url, memo
            )

    async def _handle_text(self, telegram_id: int, text: str) -> None:
        query = text.strip()
        if not query:
            return
        logger.info("Searching for %s from %s", query, telegram_id)
        results = await self._link_service.search(telegram_id, query)
        await self._telegram.send_search_results(telegram_id, query, results)
