import json

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.infrastructure.rag.korean_utils import strip_particles

_KEYWORD_WEIGHT_JINA = 0.3
_KEYWORD_WEIGHT_OG = 0.1

_RECALL_MULTIPLIER = 5
_MIN_RECALL_K = 30
_MAX_RECALL_K = 100

_MIN_RESULT_SIMILARITY = 0.30
_RELATIVE_RESULT_RATIO = 0.60


class HybridRetriever:
    """벡터 유사도 + LLM 키워드 기반 하이브리드 검색기."""

    def __init__(self, openai: AIAnalysisPort, chunk_repo: IChunkRepository) -> None:
        self._openai = openai
        self._chunk_repo = chunk_repo

    async def retrieve(self, user_id: int, query: str, top_k: int = 10) -> list[dict]:
        """Dense + LLM Keyword Overlap 하이브리드 검색.

        chunk 경로(search_similar) + OG summary_embedding 경로(search_og_links)를 병합.
        DB는 recall_k로 넓게 조회 후 keyword rescoring → link_id dedupe
        → score cutoff → 최종 top_k 반환.
        """
        [embedding] = await self._openai.embed([query])
        recall_k = min(max(top_k * _RECALL_MULTIPLIER, _MIN_RECALL_K), _MAX_RECALL_K)
        chunk_results = await self._chunk_repo.search_similar(user_id, embedding, recall_k, query_text=query)
        og_results = await self._chunk_repo.search_og_links(user_id, embedding, recall_k)
        merged = _merge_results(chunk_results, og_results)
        rescored = _rescore_with_keywords(merged, query)
        deduped = _dedupe_by_link(rescored)
        return _apply_score_cutoff(deduped)[:top_k]


def _merge_results(chunk_results: list[dict], og_results: list[dict]) -> list[dict]:
    """chunk 경로와 OG summary_embedding 경로 결과를 병합. link_id 기준 chunk 경로 우선."""
    seen: set[int] = {r["link_id"] for r in chunk_results if r.get("link_id") is not None}
    extra = [r for r in og_results if r.get("link_id") not in seen]
    return chunk_results + extra


def _build_query_variants(query: str) -> list[str]:
    """원문 + 공백제거본 + bi-gram + particle-stripped 변형 생성.

    예: "채용공고를 찾습니다" → includes:
      - "채용공고를 찾습니다" (original)
      - "채용공고를찾습니다" (compact)
      - "채용공고를 찾습니다" (bi-gram if applicable)
      - "채용공고 찾습니다" (particle-stripped)

    Korean particles (을, 를, 에서, etc.) are stripped from each token.
    """
    base = query.strip()
    variants = [base]

    # Strip particles from all tokens
    tokens = base.split()
    stripped_tokens = [strip_particles(t) for t in tokens]
    stripped_base = " ".join(stripped_tokens)
    if stripped_base and stripped_base not in variants:
        variants.append(stripped_base)

    # Compact version from original tokens
    compact = "".join(tokens)
    if compact and compact not in variants:
        variants.append(compact)

    # Compact version from particle-stripped tokens
    compact_stripped = "".join(stripped_tokens)
    if compact_stripped and compact_stripped not in variants:
        variants.append(compact_stripped)

    # Bi-gram combinations from original tokens
    for i in range(len(tokens) - 1):
        combined = tokens[i] + tokens[i + 1]
        variant = " ".join(tokens[:i] + [combined] + tokens[i + 2:])
        if variant not in variants:
            variants.append(variant)

    # Bi-gram combinations from stripped tokens
    for i in range(len(stripped_tokens) - 1):
        combined = stripped_tokens[i] + stripped_tokens[i + 1]
        variant = " ".join(stripped_tokens[:i] + [combined] + stripped_tokens[i + 2:])
        if variant not in variants:
            variants.append(variant)

    return variants


def _token_matches(query_token: str, keyword: str) -> bool:
    """부분 문자열 포함 여부, Korean particle 처리 포함.

    조건부 bidirectional matching으로 particle-attached tokens를 처리:
    1. Exact match (after lowercasing)
    2. Query token as substring of keyword (original logic)
    3. Exact match after particle stripping: "채용공고를" (stripped) == keyword "채용공고"
    4. Stripped query as substring of keyword (only if both meaningful)

    keyword in query_token 방향은 conditional only (정확히 strip 후 exact만 허용)
    → compact variant에서의 과도한 boost 방지.
    예: "공고" in "채용공고" → 허용 / "하나증권" in "하나증권공고" → 차단 (조건1만)
    """
    q = query_token.lower()
    k = keyword.lower()

    # 1. Exact match
    if q == k:
        return True

    # 2. Query token is substring of keyword (existing logic)
    if len(q) >= 2 and q in k:
        return True

    # 3. Conditional bidirectional: exact match after particle stripping
    #    This handles "채용공고를" → "채용공고" == keyword, but prevents
    #    "하나증권공고" from matching keyword "증권" (only exact after strip)
    q_stripped = strip_particles(q)
    if q_stripped != q and q_stripped == k:
        return True

    # 4. Particle-stripped substring matching (safe, only if both meaningful)
    if len(q_stripped) >= 2 and len(k) >= 2 and q_stripped in k:
        return True

    return False


def _rescore_with_keywords(results: list[dict], query: str) -> list[dict]:
    """DB similarity(base) + keyword/title overlap으로 final_score 재산출 후 내림차순 정렬.

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
        keyword_weight = (
            _KEYWORD_WEIGHT_JINA if r.get("content_source") == "jina"
            else _KEYWORD_WEIGHT_OG
        )

        overlap = 0.0
        raw_keywords = r.get("keywords")
        title = (r.get("title") or "").lower()
        link_keywords: list[str] = []
        if raw_keywords:
            try:
                parsed = json.loads(raw_keywords)
                if isinstance(parsed, list):
                    link_keywords = [k.lower() for k in parsed if isinstance(k, str) and k.strip()]
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass

        best_overlap = 0.0
        for query_tokens in all_token_sets:
            if not query_tokens:
                continue
            matched = sum(
                1 for qt in query_tokens
                if any(_token_matches(qt, kw) for kw in link_keywords)
                or (len(qt) >= 2 and qt in title)
            )
            variant_overlap = matched / len(query_tokens)
            if variant_overlap > best_overlap:
                best_overlap = variant_overlap
        overlap = best_overlap

        base_score = r.get("similarity", r.get("dense_score", 0))
        final_score = base_score * (1 - keyword_weight) + overlap * keyword_weight
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


def _apply_score_cutoff(results: list[dict]) -> list[dict]:
    """상위 결과와 점수 차이가 큰 tail noise를 제거.

    similarity < 0.30 또는 top1 * 0.60 미만이면 제외.
    최소 1개는 항상 유지.
    """
    if not results:
        return results

    top_score = results[0].get("similarity", 0)
    threshold = max(_MIN_RESULT_SIMILARITY, top_score * _RELATIVE_RESULT_RATIO)

    kept = [results[0]]
    for r in results[1:]:
        if r.get("similarity", 0) >= threshold:
            kept.append(r)
    return kept
