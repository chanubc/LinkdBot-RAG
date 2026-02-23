from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.infrastructure.llm.openai_client import OpenAIClient


class SearchService:
    def __init__(self, openai: OpenAIClient, chunk_repo: IChunkRepository) -> None:
        self._openai = openai
        self._chunk_repo = chunk_repo

    async def search(
        self, telegram_id: int, query: str, top_k: int = 5
    ) -> list[dict]:
        """시맨틱 검색."""
        [embedding] = await self._openai.embed([query])
        return await self._chunk_repo.search_similar(telegram_id, embedding, top_k)
