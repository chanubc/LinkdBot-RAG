from abc import ABC, abstractmethod

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
    ) -> Link | None: ...

    @abstractmethod
    async def save_memo(
        self,
        user_id: int,
        title: str,
        keywords: str,
        memo: str,
    ) -> Link: ...
