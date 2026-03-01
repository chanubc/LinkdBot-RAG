from abc import ABC, abstractmethod
from datetime import datetime

from app.models.link import Link


class ILinkRepository(ABC):
    @abstractmethod
    async def save_link(
        self,
        user_id: int,
        url: str,
        title: str,
        summary: str,
        category: str,
        keywords: str,
        memo: str | None = None,
        content_source: str | None = None,
        summary_embedding: list[float] | None = None,
    ) -> Link | None: ...

    @abstractmethod
    async def save_memo(
        self,
        user_id: int,
        title: str,
        keywords: str,
        memo: str,
    ) -> Link: ...

    @abstractmethod
    async def get_unread_links(self, user_id: int, limit: int = 10) -> list[Link]: ...

    # --- Phase 3: Proactive Agent ---

    @abstractmethod
    async def get_categories_by_period(
        self,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[str]: ...

    @abstractmethod
    async def get_summary_embeddings_by_period(
        self,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[list[float]]: ...

    @abstractmethod
    async def get_reactivation_candidates(
        self,
        user_id: int,
        older_than_days: int = 7,
        excluded_ids: list[int] | None = None,
    ) -> list[dict]: ...

    @abstractmethod
    async def get_all_summary_embeddings(
        self,
        user_id: int,
    ) -> list[list[float]]: ...

    @abstractmethod
    async def mark_as_read(self, link_id: int) -> None: ...
