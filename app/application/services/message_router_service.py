import logging

from app.application.ports.agent_port import AgentPort
from app.application.ports.intent_classifier_port import IntentClassifierPort
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.save_link_usecase import SaveLinkUseCase
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

    async def route(self, telegram_id: int, text: str) -> None:
        """메시지를 적절한 핸들러로 라우팅."""
        if not text.strip():
            return

        # 슬래쉬 명령어는 직접 처리 (Port 거치지 않음)
        if text.startswith("/start"):
            await self._handle_start(telegram_id)
        elif text.startswith("/help"):
            await self._handle_help(telegram_id)
        elif text.startswith("/memo"):
            memo_text = text[5:].strip()
            if memo_text:
                await self._telegram.send_message(telegram_id, "📝 메모를 저장하는 중입니다...")
                await self._save_memo_uc.execute(telegram_id, memo_text)
            else:
                await self._telegram.send_message(
                    telegram_id,
                    "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
                )
        elif text.startswith("/ask"):
            query = text[4:].strip()
            if query:
                await self._agent.run(telegram_id, query)  # Port 사용
            else:
                await self._telegram.send_message(
                    telegram_id,
                    "질문을 입력해주세요.\n예시: <code>/ask 머신러닝이란?</code>",
                )
        elif text.startswith("/search"):
            query = text[7:].strip()
            if query:
                results = await self._search_uc.execute(telegram_id, query)
                await self._telegram.send_search_results(telegram_id, query, results)
            else:
                await self._telegram.send_message(
                    telegram_id,
                    "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
                )
        # 일반 텍스트 → Intent 분류 (Port 사용)
        else:
            routed = await self._intent_classifier.classify(text)  # Port 사용
            effective_query = routed.query or text

            if routed.intent == Intent.SEARCH:
                results = await self._search_uc.execute(telegram_id, effective_query)
                await self._telegram.send_search_results(telegram_id, effective_query, results)
            elif routed.intent == Intent.MEMO:
                await self._telegram.send_message(telegram_id, "📝 메모를 저장하는 중입니다...")
                await self._save_memo_uc.execute(telegram_id, effective_query)
            elif routed.intent == Intent.ASK:
                await self._agent.run(telegram_id, effective_query)  # Port 사용
            elif routed.intent == Intent.START:
                await self._handle_start(telegram_id)
            elif routed.intent == Intent.HELP:
                await self._handle_help(telegram_id)
            else:  # UNKNOWN
                await self._telegram.send_message(
                    telegram_id,
                    "봇 사용법이 궁금하시면 /help 를 입력해보세요.",
                )

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
