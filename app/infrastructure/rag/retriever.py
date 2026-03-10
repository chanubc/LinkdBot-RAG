import json

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort

_KEYWORD_WEIGHT_JINA = 0.3
_KEYWORD_WEIGHT_OG = 0.1

_RECALL_MULTIPLIER = 5
_MIN_RECALL_K = 30
_MAX_RECALL_K = 100


class HybridRetriever:
    """벡터 유사도 + LLM 키워드 기반 하이브리드 검색기."""

    def __init__(self, openai: AIAnalysisPort, chunk_repo: IChunkRepository) -> None:
        self._openai = openai
        self._chunk_repo = chunk_repo

    async def retrieve(self, user_id: int, query: str, top_k: int = 10) -> list[dict]:
        """Dense + LLM Keyword Overlap 하이브리드 검색.

        DB는 recall_k로 넓게 조회 후 keyword rescoring, 최종 top_k만 반환.
        """
        [embedding] = await self._openai.embed([query])
        recall_k = min(max(top_k * _RECALL_MULTIPLIER, _MIN_RECALL_K), _MAX_RECALL_K)
        results = await self._chunk_repo.search_similar(user_id, embedding, recall_k, query_text=query)
        return _rescore_with_keywords(results, query)[:top_k]


def _rescore_with_keywords(results: list[dict], query: str) -> list[dict]:
    """dense_score + keyword overlap으로 final_score 재산출 후 내림차순 정렬."""
    query_tokens = {t.lower() for t in query.split() if t}
    if not query_tokens:
        return results

    rescored = []
    for r in results:
        dense_score = r.get("dense_score", r.get("similarity", 0))
        keyword_weight = (
            _KEYWORD_WEIGHT_JINA if r.get("content_source") == "jina"
            else _KEYWORD_WEIGHT_OG
        )

        overlap = 0.0
        raw_keywords = r.get("keywords")
        if raw_keywords:
            try:
                link_keywords = {k.lower() for k in json.loads(raw_keywords)}
                overlap = len(query_tokens & link_keywords) / len(query_tokens)
            except (json.JSONDecodeError, TypeError):
                pass

        final_score = dense_score * (1 - keyword_weight) + overlap * keyword_weight
        rescored.append({**r, "similarity": round(final_score, 4)})

    return sorted(rescored, key=lambda x: x["similarity"], reverse=True)
