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

    async def route(
        self, telegram_id: int, text: str, background_tasks: BackgroundTasks | None = None
    ) -> None:
        """메시지를 적절한 핸들러로 라우팅.

        Long-running 작업은 background_tasks를 통해 비동기 실행됨.
        """
        if not text.strip():
            return

        # 슬래쉬 명령어 처리
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0]
            payload = parts[1] if len(parts) > 1 else ""

            if command == "/start":
                await self._handle_start(telegram_id)
            elif command == "/help":
                await self._handle_help(telegram_id)
            elif command == "/memo":
                await self._process_memo(telegram_id, payload, background_tasks)
            elif command == "/ask":
                await self._process_ask(telegram_id, payload, background_tasks)
            elif command == "/search":
                await self._process_search(telegram_id, payload)
            return

        # 일반 텍스트 → Intent 분류 (Port 사용)
        routed = await self._intent_classifier.classify(text)
        effective_query = routed.query or text

        if routed.intent == Intent.SEARCH:
            await self._process_search(telegram_id, effective_query)
        elif routed.intent == Intent.MEMO:
            await self._process_memo(telegram_id, effective_query, background_tasks)
        elif routed.intent == Intent.ASK:
            await self._process_ask(telegram_id, effective_query, background_tasks)
        elif routed.intent == Intent.START:
            await self._handle_start(telegram_id)
        elif routed.intent == Intent.HELP:
            await self._handle_help(telegram_id)
        else:  # UNKNOWN
            await self._telegram.send_message(
                telegram_id,
                "봇 사용법이 궁금하시면 /help 를 입력해보세요.",
            )

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

        await self._telegram.send_message(telegram_id, "📝 메모를 저장하는 중입니다...")
        if background_tasks:
            background_tasks.add_task(self._save_memo_uc.execute, telegram_id, payload)
        else:
            await self._save_memo_uc.execute(telegram_id, payload)

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

        if background_tasks:
            background_tasks.add_task(self._agent.run, telegram_id, payload)
        else:
            await self._agent.run(telegram_id, payload)

    async def _process_search(self, telegram_id: int, payload: str) -> None:
        """검색 처리."""
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
            )
            return

        results = await self._search_uc.execute(telegram_id, payload)
        await self._telegram.send_search_results(telegram_id, payload, results)

    async def _handle_start(self, telegram_id: int) -> None:
        """시작 명령어 처리."""
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = user.first_name
            await self._telegram.send_welcome_connected(telegram_id, first_name)
        else:
            login_url = self._auth_service.create_login_url(telegram_id)
            await self._telegram.send_notion_connect_button(telegram_id, login_url)

    async def _handle_help(self, telegram_id: int) -> None:
        """도움말 명령어 처리."""
        await self._telegram.send_help_message(telegram_id)
