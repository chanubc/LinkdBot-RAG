import html
import re

from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.generate_weekly_report_usecase import GenerateWeeklyReportUseCase
from app.application.usecases.recall_memo_usecase import RecallMemoUseCase
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
        intent_classifier: IntentRouterPort,
        agent: KnowledgeAgentPort,
        search_uc: SearchUseCase,
        save_memo_uc: SaveMemoUseCase,
        recall_memo_uc: RecallMemoUseCase,
        weekly_report_uc: GenerateWeeklyReportUseCase,
        telegram: TelegramPort,
        user_repo: IUserRepository,
        auth_service: AuthService,
    ):
        self._intent_classifier = intent_classifier
        self._agent = agent
        self._search_uc = search_uc
        self._save_memo_uc = save_memo_uc
        self._recall_memo_uc = recall_memo_uc
        self._weekly_report_uc = weekly_report_uc
        self._telegram = telegram
        self._user_repo = user_repo
        self._auth_service = auth_service

        self._slash_handlers = {
            "/start": self._handle_start,
            "/help": self._handle_help,
            "/menu": self._handle_menu,
            "/memo": self._process_memo,
            "/ask": self._process_ask,
            "/search": self._process_search,
            "/report": self._handle_report,
            "/dashboard": self._handle_dashboard,
        }

        self._intent_handlers = {
            Intent.SEARCH: self._process_search,
            Intent.MEMO: self._process_memo,
            Intent.MEMO_RECALL: self._process_memo_recall,
            Intent.ASK: self._process_ask,
            Intent.START: self._handle_start,
            Intent.HELP: self._handle_help,
        }

    async def _run_safe(
        self,
        telegram_id: int,
        coro,
        *args,
        error_msg: str = "처리 중 오류가 발생했습니다.",
    ) -> None:
        async def safe_wrapper():
            try:
                await coro(*args)
            except Exception as e:
                logger.exception(f"Error in {coro.__name__}: {e}")
                await self._telegram.send_message(telegram_id, error_msg)

        await safe_wrapper()

    async def route(self, telegram_id: int, text: str) -> None:
        if not text.strip():
            return

        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            command = parts[0]
            payload = parts[1] if len(parts) > 1 else ""

            handler = self._slash_handlers.get(command)
            if handler:
                await handler(telegram_id, payload)
            else:
                await self._telegram.send_message(
                    telegram_id,
                    "알 수 없는 명령어입니다. /help를 입력해보세요.",
                )
            return

        if self._is_likely_ask_text(text):
            await self._process_ask(telegram_id, text)
            return

        await self._telegram.send_message(telegram_id, "🤔 분석 중입니다...")
        try:
            routed = await self._intent_classifier.classify(text)
            effective_query = routed.query or text
            if routed.intent == Intent.MEMO_RECALL:
                effective_query = (routed.query or "").strip()
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
                if routed.intent == Intent.MEMO_RECALL:
                    await handler(telegram_id, effective_query, routed.time_filter)
                else:
                    await handler(telegram_id, effective_query)
            else:
                await self._telegram.send_message(
                    telegram_id,
                    "봇 사용법이 궁금하시면 /help 를 입력해보세요.",
                )
        except Exception as e:
            logger.exception(f"Error handling intent: {e}")
            await self._telegram.send_message(telegram_id, "처리 중 오류가 발생했습니다.")

    async def _process_memo(self, telegram_id: int, payload: str) -> None:
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
            )
            return

        await self._run_safe(
            telegram_id,
            self._save_memo_uc.execute,
            telegram_id,
            payload,
            error_msg="메모 저장 중 오류가 발생했습니다.",
        )

    async def _process_ask(self, telegram_id: int, payload: str) -> None:
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "질문을 입력해주세요.\n예시: <code>/ask 머신러닝이란?</code>",
            )
            return

        await self._telegram.send_message(telegram_id, "🤖 질문을 확인했어요. 답변 준비를 시작합니다...")
        await self._run_safe(
            telegram_id,
            self._answer_and_send,
            telegram_id,
            payload,
            error_msg="질문 처리 중 오류가 발생했습니다.",
        )

    async def _process_search(self, telegram_id: int, payload: str) -> None:
        if not payload:
            await self._telegram.send_message(
                telegram_id,
                "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
            )
            return

        await self._telegram.send_message(telegram_id, "🔍 검색 요청을 받았어요. 관련 링크를 찾는 중입니다...")
        await self._run_safe(
            telegram_id,
            self._execute_search_and_send_results,
            telegram_id,
            payload,
            error_msg="검색 중 오류가 발생했습니다.",
        )

    async def _process_memo_recall(
        self,
        telegram_id: int,
        payload: str,
        time_filter: str | None = None,
    ) -> None:
        await self._run_safe(
            telegram_id,
            self._execute_recall_memo_and_send_results,
            telegram_id,
            payload,
            time_filter,
            error_msg="메모 조회 중 오류가 발생했습니다.",
        )

    async def _handle_start(self, telegram_id: int, payload: str = "") -> None:
        await self._run_safe(
            telegram_id,
            self._send_start_message,
            telegram_id,
            error_msg="/start 처리 중 오류가 발생했습니다.",
        )

    async def _handle_help(self, telegram_id: int, payload: str = "") -> None:
        await self._run_safe(
            telegram_id,
            self._telegram.send_help_message,
            telegram_id,
            error_msg="/help 처리 중 오류가 발생했습니다.",
        )

    async def _handle_menu(self, telegram_id: int, payload: str = "") -> None:
        await self._run_safe(
            telegram_id,
            self._send_menu_message,
            telegram_id,
            error_msg="메뉴를 여는 중 오류가 발생했습니다.",
        )

    async def _handle_report(self, telegram_id: int, payload: str = "") -> None:
        await self._telegram.send_message(telegram_id, "📊 주간 리포트를 준비하고 있어요...")
        await self._run_safe(
            telegram_id,
            self._generate_weekly_report,
            telegram_id,
            error_msg="주간 리포트 생성 중 오류가 발생했습니다.",
        )

    async def _send_start_message(self, telegram_id: int) -> None:
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if user and user.notion_access_token:
            first_name: str | None = user.first_name
            await self._telegram.send_welcome_connected(telegram_id, first_name)
        else:
            login_url = self._auth_service.create_login_url(telegram_id)
            await self._telegram.send_notion_connect_button(telegram_id, login_url)

    async def _send_menu_message(self, telegram_id: int) -> None:
        dashboard_url = self._build_dashboard_url(telegram_id)
        notion_url = await self._build_notion_url(telegram_id)
        await self._telegram.send_menu_message(telegram_id, dashboard_url, notion_url)

    async def _generate_weekly_report(self, telegram_id: int) -> None:
        await self._telegram.send_message(telegram_id, "🧠 저장된 관심사와 읽지 않은 링크를 정리하는 중입니다...")
        await self._weekly_report_uc.execute(telegram_id)

    async def _handle_dashboard(self, telegram_id: int, payload: str = "") -> None:
        await self._run_safe(
            telegram_id,
            self._send_dashboard_message,
            telegram_id,
            error_msg="대시보드 링크 생성 중 오류가 발생했습니다.",
        )

    async def _send_dashboard_message(self, telegram_id: int) -> None:
        await self._telegram.send_dashboard_button(telegram_id, self._build_dashboard_url(telegram_id))

    def _build_dashboard_url(self, telegram_id: int) -> str:
        from app.core.jwt import create_dashboard_token
        from app.core.config import settings

        token = create_dashboard_token(telegram_id)
        return f"{settings.DASHBOARD_URL}?token={token}"

    async def _build_notion_url(self, telegram_id: int) -> str | None:
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not user or not user.notion_database_id:
            return None
        return f"https://www.notion.so/{user.notion_database_id.replace('-', '')}"

    async def _execute_search_and_send_results(self, telegram_id: int, query: str) -> None:
        await self._telegram.send_message(telegram_id, "📚 저장된 링크를 스캔하고 있어요...")
        results = await self._search_uc.execute(telegram_id, query)
        await self._telegram.send_search_results(telegram_id, query, results)

    async def _answer_and_send(self, telegram_id: int, query: str) -> None:
        await self._telegram.send_message(telegram_id, "📚 저장된 지식과 메모를 찾는 중입니다...")
        result = await self._agent.answer(telegram_id, query)
        await self._telegram.send_ask_response(
            telegram_id,
            answer_text=result.answer,
            sources=result.sources,
        )

    async def _execute_recall_memo_and_send_results(
        self,
        telegram_id: int,
        query: str,
        time_filter: str | None = None,
    ) -> None:
        await self._telegram.send_message(telegram_id, "🗂️ 메모를 찾는 중입니다...")
        results = await self._recall_memo_uc.execute(
            telegram_id=telegram_id,
            query=query,
            time_filter=time_filter,
        )
        normalized_filter = (
            time_filter if time_filter in self._ALLOWED_TIME_FILTERS else "recent"
        )
        filter_text = html.escape(normalized_filter)
        if not results:
            await self._telegram.send_message(
                telegram_id,
                f"🗂️ 메모를 찾지 못했어요. (기간: {filter_text})",
            )
            return

        lines = [f"🗂️ <b>메모 조회 결과</b> (기간: {filter_text})\n"]
        for i, r in enumerate(results, 1):
            memo = html.escape((r.get("memo") or "").strip()[:120] or "내용 없음")
            created_at = (r.get("created_at") or "")[:10]
            date_text = f" · {created_at}" if created_at else ""
            lines.append(f"{i}. {memo}{date_text}")

        await self._telegram.send_message(telegram_id, "\n".join(lines))

    @staticmethod
    def _is_likely_ask_text(text: str) -> bool:
        normalized = text.strip().lower()
        if not normalized:
            return False

        classifier_first_substrings = (
            "검색",
            "찾아",
            "search",
            "find",
            "memo",
            "메모",
            "어제",
            "오늘",
            "지난",
            "최근",
            "recall",
            "기록",
            "저장",
            "usage",
            "guide",
            "instruction",
            "getting started",
            "도움",
            "사용법",
            "사용",
            "시작",
            "notion",
            "connect",
            "연동",
            "로그인",
            "login",
            "report",
            "리포트",
            "브리핑",
        )
        classifier_first_words = ("help", "use", "start", "menu")

        if any(hint in normalized for hint in classifier_first_substrings):
            return False
        if any(re.search(rf"\b{word}\b", normalized) for word in classifier_first_words):
            return False

        question_substrings = (
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
            "why",
            "explain",
            "difference",
        )
        question_words = ("what", "how")

        return any(hint in normalized for hint in question_substrings) or any(
            re.search(rf"\b{word}\b", normalized) for word in question_words
        )

    _ALLOWED_TIME_FILTERS = {"today", "yesterday", "last_7_days", "recent"}
