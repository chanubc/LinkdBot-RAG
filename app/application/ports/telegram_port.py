from abc import ABC, abstractmethod


class TelegramPort(ABC):
    """Telegram API 통신 Port."""

    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> None:
        """메시지 전송."""
        pass

    @abstractmethod
    async def send_notion_connect_button(self, chat_id: int, login_url: str) -> None:
        """Notion 연동 버튼 전송."""
        pass

    @abstractmethod
    async def send_link_saved_message(
        self, chat_id: int, text: str, notion_url: str | None = None
    ) -> None:
        """링크 저장 완료 메시지 전송."""
        pass

    @abstractmethod
    async def answer_callback_query(self, callback_query_id: str) -> None:
        """콜백 쿼리 응답."""
        pass

    @abstractmethod
    async def send_help_message(self, chat_id: int) -> None:
        """도움말 메시지 전송."""
        pass

    @abstractmethod
    async def send_welcome_connected(
        self, chat_id: int, first_name: str | None = None
    ) -> None:
        """Notion 연동 완료 메시지 전송."""
        pass

    @abstractmethod
    async def send_search_results(self, chat_id: int, query: str, results: list[dict]) -> None:
        """검색 결과 전송."""
        pass

    @abstractmethod
    async def set_webhook(self, url: str) -> None:
        """Telegram 웹훅 등록."""
        pass

    @abstractmethod
    async def register_commands(self) -> bool:
        """봇 명령어 자동완성 등록 (setMyCommands)."""
        pass

    @abstractmethod
    async def send_weekly_report(
        self,
        chat_id: int,
        text: str,
        link_id: int | None = None,
    ) -> None:
        """주간 리포트 전송. link_id 있으면 [읽음 처리] 인라인 버튼 포함."""
        pass
