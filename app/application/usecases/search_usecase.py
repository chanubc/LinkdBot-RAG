from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever, _build_search_queries


class SearchUseCase:
    def __init__(self, retriever: HybridRetriever, reranker: SimpleReranker) -> None:
        self._retriever = retriever
        self._reranker = reranker

    async def execute(self, user_id: int, query: str, top_k: int = 5) -> list[dict]:
        """Search-first retrieval with query normalization fallback."""
        queries = _build_search_queries(query)
        raw_results = await self._retriever.retrieve(
            user_id,
            query,
            top_k * 2,
            search_queries=queries,
        )
        return self._reranker.rerank(raw_results, top_k)
