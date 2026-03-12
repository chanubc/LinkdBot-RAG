from abc import ABC, abstractmethod


class NotionPort(ABC):
    """Notion API 통신 Port."""

    @abstractmethod
    async def exchange_code(self, code: str) -> dict:
        """OAuth authorization code → access token 교환."""
        pass

    @abstractmethod
    async def get_accessible_page_id(self, access_token: str) -> str | None:
        """봇이 접근 가능한 첫 번째 페이지 ID 반환."""
        pass

    @abstractmethod
    async def create_database(self, access_token: str, parent_page_id: str) -> str:
        """LinkdBot 전용 Notion 데이터베이스 생성 후 database_id 반환."""
        pass

    @abstractmethod
    async def create_database_entry(
        self,
        access_token: str,
        database_id: str,
        title: str,
        category: str,
        keywords: list[str],
        summary: str,
        content: str | None = None,
        url: str | None = None,
        memo: str | None = None,
    ) -> str:
        """Notion DB에 행 추가 후 페이지 URL 반환."""
        pass
