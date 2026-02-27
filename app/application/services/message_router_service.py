import logging

from fastapi import BackgroundTasks

from app.application.ports.agent_port import AgentPort
from app.application.ports.intent_classifier_port import IntentClassifierPort
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.usecases.search_usecase import SearchUseCase
from app.application.services.auth_service import AuthService
from app.domain.entities.intent import Intent
from app.domain.repositories.i_user_repository import IUserRepository

logger = logging.getLogger(__name__)


class MessageRouterService:
    """
    책임: 모든 메시지 처리 (슬래쉬 명령어 + Intent 분류)

    Port를 통해 의존성 주입받으므로:
    - OpenAI ↔ Anthropic/LangChain 교체 가능
    - KnowledgeAgent ↔ LangGraph 교체 가능
    """

    def __init__(
        self,
        intent_classifier: IntentClassifierPort,  # Port: Intent 분류
        agent: AgentPort,  # Port: AI Agent 실행
        search_uc: SearchUseCase,
        save_memo_uc: SaveMemoUseCase,
        telegram: TelegramPort,
        user_repo: IUserRepository,
        auth_service: AuthService,
    ):
        self._intent_classifier = intent_classifier  # Port 의존
        self._agent = agent  # Port 의존
        self._search_uc = search_uc
        self._save_memo_uc = save_memo_uc
        self._telegram = telegram
        self._user_repo = user_repo
        self._auth_service = auth_service

        # Slash command handlers map (OCP: new commands don't require editing route())
        self._slash_handlers = {
            "/start": self._handle_start_command,
            "/help": self._handle_help_command,
            "/memo": self._handle_memo_command,
            "/ask": self._handle_ask_command,
            "/search": self._handle_search_command,
        }

        # Intent handlers map (OCP: new intents don't require editing route())
        self._intent_handlers = {
            Intent.SEARCH: self._handle_search_intent,
            Intent.MEMO: self._handle_memo_intent,
            Intent.ASK: self._handle_ask_intent,
            Intent.START: self._handle_start_intent,
            Intent.HELP: self._handle_help_intent,
        }

    async def _run_in_background(
        self, background_tasks: BackgroundTasks | None, coro, *args
    ) -> None:
        """Execute coroutine in background or directly based on availability.

        Args:
            background_tasks: FastAPI BackgroundTasks instance (optional)
            coro: Coroutine function to execute
            *args: Arguments to pass to coroutine
        """
        if background_tasks:
            background_tasks.add_task(coro, *args)
        else:
            await coro(*args)

    async def route(
        self, telegram_id: int, text: str, background_tasks: BackgroundTasks | None = None
    ) -> None:
        """메시지를 적절한 핸들러로 라우팅.

        Long-running 작업은 background_tasks를 통해 비동기 실행됨.
        """
        if not text.strip():
            return

        # 슬래쉬 명령어 처리 (Dictionary dispatch)
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0]
            payload = parts[1] if len(parts) > 1 else ""

            handler = self._slash_handlers.get(command)
            if handler:
                await handler(telegram_id, payload, background_tasks)
            return

        # 일반 텍스트 → Intent 분류 (Port 사용)
        try:
            routed = await self._intent_classifier.classify(text)
            effective_query = routed.query or text
        except Exception as e:
            logger.exception("Error classifying intent: %s", e)
            await self._telegram.send_message(
                telegram_id,
                "봇 사용법이 궁금하시면 /help 를 입력해보세요.",
            )
            return

        try:
            handler = self._intent_handlers.get(routed.intent)
            if handler:
                await handler(telegram_id, effective_query, background_tasks)
            else:  # UNKNOWN intent
                await self._telegram.send_message(
                    telegram_id,
                    "봇 사용법이 궁금하시면 /help 를 입력해보세요.",
                )
        except Exception as e:
            logger.exception("Error handling intent: %s", e)
            await self._telegram.send_message(telegram_id, "처리 중 오류가 발생했습니다.")

    async def _process_memo(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """메모 저장 처리."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
            )
            return

        try:
            await self._telegram.send_message(telegram_id, "📝 메모를 저장하는 중입니다...")
            await self._run_in_background(
                background_tasks, self._save_memo_uc.execute, telegram_id, payload
            )
        except Exception as e:
            logger.exception("Error saving memo: %s", e)
            await self._telegram.send_message(telegram_id, "메모 저장 중 오류가 발생했습니다.")

    async def _process_ask(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """질문/에이전트 실행 처리."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "질문을 입력해주세요.\n예시: <code>/ask 머신러닝이란?</code>",
            )
            return

        try:
            await self._run_in_background(background_tasks, self._agent.run, telegram_id, payload)
        except Exception as e:
            logger.exception("Error running agent: %s", e)
            await self._telegram.send_message(telegram_id, "질문 처리 중 오류가 발생했습니다.")

    async def _process_search(self, telegram_id: int, payload: str) -> None:
        """검색 처리."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
            )
            return

        try:
            results = await self._search_uc.execute(telegram_id, payload)
            await self._telegram.send_search_results(telegram_id, payload, results)
        except Exception as e:
            logger.exception("Error searching: %s", e)
            await self._telegram.send_message(telegram_id, "검색 중 오류가 발생했습니다.")

    async def _handle_start(self, telegram_id: int) -> None:
        """시작 명령어 처리."""
        try:
            user = await self._user_repo.get_by_telegram_id(telegram_id)
            if user and user.notion_access_token:
                first_name: str | None = user.first_name
                await self._telegram.send_welcome_connected(telegram_id, first_name)
            else:
                login_url = self._auth_service.create_login_url(telegram_id)
                await self._telegram.send_notion_connect_button(telegram_id, login_url)
        except Exception as e:
            logger.exception("Error handling start: %s", e)
            await self._telegram.send_message(telegram_id, "/start 처리 중 오류가 발생했습니다.")

    async def _handle_help(self, telegram_id: int) -> None:
        """도움말 명령어 처리 (내부 구현)."""
        try:
            await self._telegram.send_help_message(telegram_id)
        except Exception as e:
            logger.exception("Error handling help: %s", e)
            await self._telegram.send_message(telegram_id, "/help 처리 중 오류가 발생했습니다.")

    # --- Unified Slash Command Handlers (for dictionary dispatch) ---

    async def _handle_start_command(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Slash command /start handler."""
        await self._handle_start(telegram_id)

    async def _handle_help_command(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Slash command /help handler."""
        await self._handle_help(telegram_id)

    async def _handle_memo_command(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Slash command /memo handler."""
        await self._process_memo(telegram_id, payload, background_tasks)

    async def _handle_ask_command(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Slash command /ask handler."""
        await self._process_ask(telegram_id, payload, background_tasks)

    async def _handle_search_command(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Slash command /search handler."""
        await self._process_search(telegram_id, payload)

    # --- Unified Intent Handlers (for dictionary dispatch) ---

    async def _handle_search_intent(
        self, telegram_id: int, query: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Intent.SEARCH handler."""
        await self._process_search(telegram_id, query)

    async def _handle_memo_intent(
        self, telegram_id: int, query: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Intent.MEMO handler."""
        await self._process_memo(telegram_id, query, background_tasks)

    async def _handle_ask_intent(
        self, telegram_id: int, query: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Intent.ASK handler."""
        await self._process_ask(telegram_id, query, background_tasks)

    async def _handle_start_intent(
        self, telegram_id: int, query: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Intent.START handler."""
        await self._handle_start(telegram_id)

    async def _handle_help_intent(
        self, telegram_id: int, query: str, background_tasks: BackgroundTasks | None
    ) -> None:
        """Intent.HELP handler."""
        await self._handle_help(telegram_id)
