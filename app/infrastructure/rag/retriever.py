from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort


class HybridRetriever:
    """벡터 유사도 기반 검색기. Phase 3+에서 키워드 하이브리드로 확장."""

    def __init__(self, openai: AIAnalysisPort, chunk_repo: IChunkRepository) -> None:
        self._openai = openai
        self._chunk_repo = chunk_repo

    async def retrieve(self, user_id: int, query: str, top_k: int = 10) -> list[dict]:
        """쿼리 임베딩 → Hybrid (Dense + Sparse) 검색."""
        [embedding] = await self._openai.embed([query])
        return await self._chunk_repo.search_similar(user_id, embedding, top_k, query_text=query)
