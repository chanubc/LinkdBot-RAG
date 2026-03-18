from abc import ABC, abstractmethod


class IChunkRepository(ABC):
    @abstractmethod
    async def save_chunks(
        self,
        link_id: int,
        chunks: list[tuple[str, list[float]]],
    ) -> None: ...

    @abstractmethod
    async def search_similar(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        query_text: str = "",
    ) -> list[dict]: ...

    @abstractmethod
    async def search_og_links(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]: ...

    @abstractmethod
    async def search_bm25(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
    ) -> list[dict]: ...
