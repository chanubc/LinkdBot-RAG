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

        DB는 recall_k로 넓게 조회 후 keyword rescoring → link_id dedupe → 최종 top_k 반환.
        """
        [embedding] = await self._openai.embed([query])
        recall_k = min(max(top_k * _RECALL_MULTIPLIER, _MIN_RECALL_K), _MAX_RECALL_K)
        results = await self._chunk_repo.search_similar(user_id, embedding, recall_k, query_text=query)
        rescored = _rescore_with_keywords(results, query)
        return _dedupe_by_link(rescored)[:top_k]


def _build_query_variants(query: str) -> list[str]:
    """원문 + 공백제거본 + bi-gram 결합본으로 query 변형 생성.

    예: "하나 증권 공고" → ["하나 증권 공고", "하나증권공고", "하나증권 공고", "하나 증권공고"]
    """
    base = query.strip()
    variants = [base]

    compact = "".join(base.split())
    if compact and compact not in variants:
        variants.append(compact)

    tokens = base.split()
    for i in range(len(tokens) - 1):
        combined = tokens[i] + tokens[i + 1]
        variant = " ".join(tokens[:i] + [combined] + tokens[i + 2:])
        if variant not in variants:
            variants.append(variant)

    return variants


def _token_matches(query_token: str, keyword: str) -> bool:
    """부분 문자열 포함 여부로 매칭 판단. 길이 2 이상에서만 substring match 허용."""
    q = query_token.lower()
    k = keyword.lower()
    if q == k:
        return True
    if len(q) >= 2 and q in k:
        return True
    if len(k) >= 2 and k in q:
        return True
    return False


def _rescore_with_keywords(results: list[dict], query: str) -> list[dict]:
    """dense_score + keyword overlap으로 final_score 재산출 후 내림차순 정렬.

    query 변형(원문/공백제거/bi-gram)별 overlap 중 최댓값을 사용.
    """
    all_token_sets = [
        {t.lower() for t in v.split() if t}
        for v in _build_query_variants(query)
    ]
    if not any(all_token_sets):
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
                parsed = json.loads(raw_keywords)
                if not isinstance(parsed, list):
                    parsed = []
                link_keywords = [k.lower() for k in parsed if isinstance(k, str) and k.strip()]
                best_overlap = 0.0
                for query_tokens in all_token_sets:
                    if not query_tokens:
                        continue
                    matched = sum(
                        1 for qt in query_tokens
                        if any(_token_matches(qt, kw) for kw in link_keywords)
                    )
                    variant_overlap = matched / len(query_tokens)
                    if variant_overlap > best_overlap:
                        best_overlap = variant_overlap
                overlap = best_overlap
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        final_score = dense_score * (1 - keyword_weight) + overlap * keyword_weight
        rescored.append({**r, "similarity": round(final_score, 4)})

    return sorted(rescored, key=lambda x: x["similarity"], reverse=True)


def _dedupe_by_link(results: list[dict]) -> list[dict]:
    """link_id 기준 중복 제거, 최고 점수 청크 유지."""
    best_by_link: dict[int, dict] = {}
    for r in results:
        link_id = r.get("link_id")
        if link_id is None:
            continue
        prev = best_by_link.get(link_id)
        if prev is None or r.get("similarity", 0) > prev.get("similarity", 0):
            best_by_link[link_id] = r
    return sorted(best_by_link.values(), key=lambda x: x.get("similarity", 0), reverse=True)
