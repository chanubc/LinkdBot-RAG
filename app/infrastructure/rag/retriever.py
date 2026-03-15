import json

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.infrastructure.rag.korean_utils import morpheme_tokenize

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
    """원문 + 공백제거본 + bi-gram + morpheme 변형 생성.

    예: "하나 증권 채용" → includes:
      - "하나 증권 채용" (original)
      - "하나증권채용" (compact)
      - "하나증권 채용" (bi-gram: tokens 0+1 joined)
      - "하나 증권채용" (bi-gram: tokens 1+2 joined)
      - morpheme-tokenized variants (Kiwi splits compounds + strips particles)

    예: "채용공고를" → includes:
      - "채용공고를" (original)
      - "채용공고를" (compact, same)
      - "채용 공고" (morpheme: compound split + particle stripped)
      - "채용공고" (compact morpheme)
    """
    base = query.strip()
    variants = [base]

    tokens = base.split()

    # Compact version from original tokens
    compact = "".join(tokens)
    if compact and compact not in variants:
        variants.append(compact)

    # Bi-gram combinations from original tokens
    for i in range(len(tokens) - 1):
        combined = tokens[i] + tokens[i + 1]
        variant = " ".join(tokens[:i] + [combined] + tokens[i + 2:])
        if variant not in variants:
            variants.append(variant)

    # Morpheme-tokenized variant (Kiwi splits compounds + strips particles)
    # e.g. "채용공고를" → "채용 공고"
    morpheme_base = morpheme_tokenize(base)
    if morpheme_base and morpheme_base not in variants:
        variants.append(morpheme_base)

    # Compact morpheme variant
    morpheme_compact = "".join(morpheme_base.split())
    if morpheme_compact and morpheme_compact not in variants:
        variants.append(morpheme_compact)

    return variants


def _token_matches(query_token: str, keyword: str) -> bool:
    """부분 문자열 포함 여부.

    morpheme_tokenize가 _build_query_variants에서 이미 particle 제거 + compound 분리를
    처리하므로, 여기서는 단순 exact/substring 매칭만 수행.

    예: "공고" in "채용공고" → True / "하나증권" in "하나증권공고" → False
    """
    q = query_token.lower()
    k = keyword.lower()

    if q == k:
        return True

    if len(q) >= 2 and q in k:
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
