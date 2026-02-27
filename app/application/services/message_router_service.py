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
        # 모든 핸들러가 동일한 시그니처를 가지므로 직접 메서드 참조 가능
        self._slash_handlers = {
            "/start": self._handle_start,
            "/help": self._handle_help,
            "/memo": self._process_memo,
            "/ask": self._process_ask,
            "/search": self._process_search,
        }

        # Intent handlers map (OCP: new intents don't require editing route())
        self._intent_handlers = {
            Intent.SEARCH: self._process_search,
            Intent.MEMO: self._process_memo,
            Intent.ASK: self._process_ask,
            Intent.START: self._handle_start,
            Intent.HELP: self._handle_help,
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
            else:
                # Unknown command feedback
                await self._telegram.send_message(
                    telegram_id,
                    "알 수 없는 명령어입니다. /help를 입력해보세요.",
                )
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
        """메모 저장 처리 (비동기 피드백 포함)."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
            )
            return

        # 웹훅은 즉시 응답, SaveMemoUseCase 내부에서 모든 피드백 관리
        try:
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

    async def _process_search(
        self, telegram_id: int, payload: str, background_tasks: BackgroundTasks | None = None
    ) -> None:
        """검색 처리 (비동기 결과 반환)."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
            )
            return

        # 웹훅은 즉시 응답, 검색과 결과 전송은 background (검색 + 결과 전송을 한 번에)
        try:
            await self._run_in_background(
                background_tasks, self._execute_search_and_send_results, telegram_id, payload
            )
        except Exception as e:
            logger.exception("Error searching: %s", e)
            await self._telegram.send_message(telegram_id, "검색 중 오류가 발생했습니다.")

    async def _handle_start(
        self, telegram_id: int, payload: str = "", background_tasks: BackgroundTasks | None = None
    ) -> None:
        """시작 명령어 처리 (비동기 피드백)."""
        # 웹훅은 즉시 응답, 실제 처리는 background
        try:
            await self._run_in_background(
                background_tasks, self._send_start_message, telegram_id
            )
        except Exception as e:
            logger.exception("Error handling start: %s", e)
            await self._telegram.send_message(telegram_id, "/start 처리 중 오류가 발생했습니다.")

    async def _handle_help(
        self, telegram_id: int, payload: str = "", background_tasks: BackgroundTasks | None = None
    ) -> None:
        """도움말 명령어 처리 (비동기 피드백)."""
        # 웹훅은 즉시 응답, 도움말 메시지는 background로 전송
        try:
            await self._run_in_background(
                background_tasks, self._telegram.send_help_message, telegram_id
            )
        except Exception as e:
            logger.exception("Error handling help: %s", e)
            await self._telegram.send_message(telegram_id, "/help 처리 중 오류가 발생했습니다.")

    async def _send_start_message(self, telegram_id: int) -> None:
        """Start 명령어 응답 메시지 전송."""
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = user.first_name
            await self._telegram.send_welcome_connected(telegram_id, first_name)
        else:
            login_url = self._auth_service.create_login_url(telegram_id)
            await self._telegram.send_notion_connect_button(telegram_id, login_url)

    async def _execute_search_and_send_results(self, telegram_id: int, query: str) -> None:
        """검색 실행 및 결과 전송 (background에서 실행)."""
        try:
            await self._telegram.send_message(telegram_id, "🔍 검색 중입니다...")
            results = await self._search_uc.execute(telegram_id, query)
            await self._telegram.send_search_results(telegram_id, query, results)
        except Exception as e:
            logger.exception("Error executing search: %s", e)
            await self._telegram.send_message(telegram_id, "검색 중 오류가 발생했습니다.")

