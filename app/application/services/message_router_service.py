from fastapi import BackgroundTasks

from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.usecases.search_usecase import SearchUseCase
from app.application.services.auth_service import AuthService
from app.domain.entities.intent import Intent
from app.domain.repositories.i_user_repository import IUserRepository

from app.core.logger import logger


class MessageRouterService:
    """
    책임: 모든 메시지 처리 (슬래쉬 명령어 + Intent 분류)

    Port를 통해 의존성 주입받으므로:
    - OpenAI ↔ Anthropic/LangChain 교체 가능
    - KnowledgeAgent ↔ LangGraph 교체 가능
    """

    def __init__(
        self,
        intent_classifier: IntentRouterPort,  # Port: LLM 분기 결정
        agent: KnowledgeAgentPort,  # Port: 지식 처리 실행
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
            "/dashboard": self._handle_dashboard,
        }

        # Intent handlers map (OCP: new intents don't require editing route())
        self._intent_handlers = {
            Intent.SEARCH: self._process_search,
            Intent.MEMO: self._process_memo,
            Intent.ASK: self._process_ask,
            Intent.START: self._handle_start,
            Intent.HELP: self._handle_help,
        }

    async def _run_safe(
        self,
        telegram_id: int,
        background_tasks: BackgroundTasks | None,
        coro,
        *args,
        error_msg: str = "처리 중 오류가 발생했습니다."
    ) -> None:
        """Execute coroutine safely with centralized error handling.

        Args:
            telegram_id: Telegram user ID
            background_tasks: FastAPI BackgroundTasks instance (optional)
            coro: Coroutine function to execute
            *args: Arguments to pass to coroutine
            error_msg: Error message to send on failure

        모든 에러 처리가 이 메서드 한 곳에서 통합됨.
        """
        async def safe_wrapper():
            try:
                await coro(*args)
            except Exception as e:
                logger.exception(f"Error in {coro.__name__}: {e}")
                await self._telegram.send_message(telegram_id, error_msg)

        if background_tasks:
            background_tasks.add_task(safe_wrapper)
        else:
            await safe_wrapper()

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

        # 일반 텍스트 → 즉시 1차 응답 후 Intent 분류 + 처리
        if self._is_likely_ask_text(text):
            await self._process_ask(telegram_id, text, background_tasks)
            return

        await self._telegram.send_message(telegram_id, "🤔 분석 중입니다...")
        try:
            routed = await self._intent_classifier.classify(text)
            effective_query = routed.query or text
        except Exception as e:
            logger.exception(f"Error classifying intent: {e}")
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
            logger.exception(f"Error handling intent: {e}")
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
        # 에러 처리는 _run_safe에서 통합 관리
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._save_memo_uc.execute,
            telegram_id,
            payload,
            error_msg="메모 저장 중 오류가 발생했습니다."
        )

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

        # 에러 처리는 _run_safe에서 통합 관리
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._agent.run,
            telegram_id,
            payload,
            error_msg="질문 처리 중 오류가 발생했습니다."
        )

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
        # 에러 처리는 _run_safe에서 통합 관리
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._execute_search_and_send_results,
            telegram_id,
            payload,
            error_msg="검색 중 오류가 발생했습니다."
        )

    async def _handle_start(
        self, telegram_id: int, payload: str = "", background_tasks: BackgroundTasks | None = None
    ) -> None:
        """시작 명령어 처리 (비동기 피드백)."""
        # 웹훅은 즉시 응답, 실제 처리는 background
        # 에러 처리는 _run_safe에서 통합 관리
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._send_start_message,
            telegram_id,
            error_msg="/start 처리 중 오류가 발생했습니다."
        )

    async def _handle_help(
        self, telegram_id: int, payload: str = "", background_tasks: BackgroundTasks | None = None
    ) -> None:
        """도움말 명령어 처리 (비동기 피드백)."""
        # 웹훅은 즉시 응답, 도움말 메시지는 background로 전송
        # 에러 처리는 _run_safe에서 통합 관리
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._telegram.send_help_message,
            telegram_id,
            error_msg="/help 처리 중 오류가 발생했습니다."
        )

    async def _send_start_message(self, telegram_id: int) -> None:
        """Start 명령어 응답 메시지 전송.

        에러는 _run_safe에서 통합 관리되므로 순수 로직만 담당.
        """
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = user.first_name
            await self._telegram.send_welcome_connected(telegram_id, first_name)
        else:
            login_url = self._auth_service.create_login_url(telegram_id)
            await self._telegram.send_notion_connect_button(telegram_id, login_url)

    async def _handle_dashboard(
        self, telegram_id: int, payload: str = "", background_tasks: BackgroundTasks | None = None
    ) -> None:
        """개인 대시보드 링크 발송 (JWT stateless — StateStore 불필요)."""
        await self._run_safe(
            telegram_id,
            background_tasks,
            self._send_dashboard_message,
            telegram_id,
            error_msg="대시보드 링크 생성 중 오류가 발생했습니다.",
        )

    async def _send_dashboard_message(self, telegram_id: int) -> None:
        from app.core.jwt import create_dashboard_token
        from app.core.config import settings

        token = create_dashboard_token(telegram_id)
        url = f"{settings.DASHBOARD_URL}?token={token}"
        await self._telegram.send_dashboard_button(telegram_id, url)

    async def _execute_search_and_send_results(self, telegram_id: int, query: str) -> None:
        """검색 실행 및 결과 전송 (background에서 실행).

        에러는 _run_safe에서 통합 관리되므로 순수 로직만 담당.
        """
        await self._telegram.send_message(telegram_id, "🔍 검색 중입니다...")
        results = await self._search_uc.execute(telegram_id, query)
        await self._telegram.send_search_results(telegram_id, query, results)

    @staticmethod
    def _is_likely_ask_text(text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False

        # 검색/메모 신호가 강하면 classifier에 맡긴다.
        classifier_first_hints = (
            "검색",
            "찾아",
            "search",
            "find",
            "memo",
            "메모",
            "기록",
            "저장",
            "help",
            "use",
            "usage",
            "guide",
            "instruction",
            "getting started",
            "도움",
            "사용법",
            "사용",
            "start",
            "시작",
            "notion",
            "connect",
            "연동",
            "로그인",
            "login",
        )
        if any(hint in normalized for hint in classifier_first_hints):
            return False

        question_hints = (
            "?",
            "？",
            "무엇",
            "뭐",
            "왜",
            "어떻게",
            "알려",
            "설명",
            "정리",
            "궁금",
            "what",
            "why",
            "how",
            "explain",
            "difference",
        )
        return any(hint in normalized for hint in question_hints)
