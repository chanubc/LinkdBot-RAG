from abc import ABC, abstractmethod

from app.domain.entities.knowledge_source import KnowledgeSource


class TelegramPort(ABC):
    """Telegram API 통신 Port."""

    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> None:
        pass

    @abstractmethod
    async def send_notion_connect_button(self, chat_id: int, login_url: str) -> None:
        pass

    @abstractmethod
    async def send_link_saved_message(
        self, chat_id: int, text: str, notion_url: str | None = None
    ) -> None:
        pass

    @abstractmethod
    async def answer_callback_query(self, callback_query_id: str) -> None:
        pass

    @abstractmethod
    async def send_help_message(self, chat_id: int) -> None:
        pass

    @abstractmethod
    async def send_welcome_connected(
        self, chat_id: int, first_name: str | None = None
    ) -> None:
        pass

    @abstractmethod
    async def send_search_results(self, chat_id: int, query: str, results: list[dict]) -> None:
        pass

    @abstractmethod
    async def send_ask_response(
        self,
        chat_id: int,
        answer_text: str,
        sources: list[KnowledgeSource],
    ) -> None:
        pass

    @abstractmethod
    async def send_menu_message(
        self,
        chat_id: int,
        dashboard_url: str,
        notion_url: str | None,
    ) -> None:
        pass

    @abstractmethod
    async def set_webhook(self, url: str) -> None:
        pass

    @abstractmethod
    async def register_commands(self) -> bool:
        pass

    @abstractmethod
    async def send_weekly_report(
        self,
        chat_id: int,
        text: str,
        link_id: int | None = None,
    ) -> None:
        pass

    @abstractmethod
    async def send_dashboard_button(self, chat_id: int, dashboard_url: str) -> None:
        pass
