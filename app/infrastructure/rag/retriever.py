import asyncio
import json
import re

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.infrastructure.rag.korean_utils import strip_particles

_KEYWORD_WEIGHT_JINA = 0.3
_KEYWORD_WEIGHT_OG = 0.1

_RECALL_MULTIPLIER = 5
_MIN_RECALL_K = 30
_MAX_RECALL_K = 100
_BM25_RECALL_MULTIPLIER = 2
_MIN_BM25_K = 10
_MAX_BM25_K = 30

_MIN_RESULT_SIMILARITY = 0.30
_RELATIVE_RESULT_RATIO = 0.60
_TRAILING_PUNCTUATION = "!?.,:;)]}\"'”’"
_SEARCH_FILLER_TAILS = {
    "링크",
    "관련",
    "자료",
    "내용",
}
_SEARCH_COMMAND_TAILS = {
    "가져와",
    "가져와줘",
    "찾아줘",
    "보여줘",
    "알려줘",
    "줘",
    "좀",
}
_HANGUL_COMPOUND_RE = re.compile(r"^[가-힣]{4}$")


class HybridRetriever:
    """벡터 유사도 + LLM 키워드 기반 하이브리드 검색기."""

    def __init__(self, openai: AIAnalysisPort, chunk_repo: IChunkRepository) -> None:
        self._openai = openai
        self._chunk_repo = chunk_repo

    async def retrieve(
        self,
        user_id: int,
        query: str,
        top_k: int = 10,
        *,
        search_queries: list[str] | None = None,
    ) -> list[dict]:
        """Dense + LLM Keyword Overlap 하이브리드 검색.

        chunk 경로(search_similar) + BM25 lexical 경로(search_bm25)
        + OG summary_embedding 경로(search_og_links)를 병합.
        SearchUseCase can supply multiple lexical `search_queries`, but the
        embedding for `query` is computed only once and reused across those
        lexical fan-out passes.
        """
        [embedding] = await self._openai.embed([query])
        recall_k = min(max(top_k * _RECALL_MULTIPLIER, _MIN_RECALL_K), _MAX_RECALL_K)
        bm25_k = min(max(top_k * _BM25_RECALL_MULTIPLIER, _MIN_BM25_K), _MAX_BM25_K)
        og_results = await self._chunk_repo.search_og_links(user_id, embedding, recall_k)

        merged_across_queries: list[dict] = []
        seen_queries: set[str] = set()
        query_candidates = search_queries or _build_search_queries(query)

        for query_text in query_candidates:
            candidate = query_text.strip()
            if not candidate or candidate in seen_queries:
                continue
            seen_queries.add(candidate)

            chunk_results, bm25_results = await asyncio.gather(
                self._chunk_repo.search_similar(
                    user_id,
                    embedding,
                    recall_k,
                    query_text=candidate,
                ),
                self._chunk_repo.search_bm25(
                    user_id,
                    _build_bm25_query(candidate),
                    bm25_k,
                ),
            )
            merged = _merge_results(chunk_results, og_results, bm25_results)
            rescored = _rescore_with_keywords(merged, candidate)
            deduped = _dedupe_by_link(rescored)
            merged_across_queries = _merge_results(merged_across_queries, deduped)

        final_results = _dedupe_by_link(merged_across_queries)
        return _apply_score_cutoff(final_results)[:top_k]


def _merge_results(*result_sets: list[dict]) -> list[dict]:
    """Dense/OG/BM25 결과를 병합하고, 같은 link 중 더 강한 후보로 업그레이드한다."""
    ordered: list[dict] = []
    index_by_link: dict[int, int] = {}

    for result_set in result_sets:
        for result in result_set:
            link_id = result.get("link_id")
            if link_id is None:
                ordered.append(result)
                continue

            existing_index = index_by_link.get(link_id)
            if existing_index is None:
                index_by_link[link_id] = len(ordered)
                ordered.append(result)
                continue

            existing = ordered[existing_index]
            if result.get("similarity", 0) > existing.get("similarity", 0):
                ordered[existing_index] = result

    return ordered


def _build_query_variants(query: str) -> list[str]:
    """원문 + 공백제거본 + bi-gram + particle-stripped 변형 생성.

    예: "하나 증권 채용" → includes:
      - "하나 증권 채용" (original)
      - "하나증권채용" (compact)
      - "하나증권 채용" (bi-gram: tokens 0+1 joined)
      - "하나 증권채용" (bi-gram: tokens 1+2 joined)
      - particle-stripped variants of each above

    예: "채용공고를 찾습니다" → includes:
      - "채용공고를 찾습니다" (original)
      - "채용공고 찾습니다" (particle-stripped)

    Korean particles (을, 를, 에서, etc.) are stripped from each token.
    """
    base = query.strip()
    variants = [base]

    cleaned_tokens = [_strip_trailing_punctuation(t) for t in base.split()]
    tokens = [t for t in cleaned_tokens if t]
    cleaned_base = " ".join(tokens)
    if cleaned_base and cleaned_base not in variants:
        variants.append(cleaned_base)

    # Strip particles from all tokens
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

    split_variant = " ".join(_split_hangul_compound_token(token) for token in stripped_tokens)
    if split_variant and split_variant not in variants:
        variants.append(split_variant)

    return variants


def _build_search_queries(query: str) -> list[str]:
    """Build search-specific lexical query family for fallback widening."""
    base = query.strip()
    if not base:
        return []

    queries = [base]

    tokens = [_strip_trailing_punctuation(t) for t in base.split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return queries

    cleaned = " ".join(tokens)
    if cleaned not in queries:
        queries.append(cleaned)

    core_tokens = tokens[:]
    while core_tokens and core_tokens[-1] in (_SEARCH_FILLER_TAILS | _SEARCH_COMMAND_TAILS):
        core_tokens.pop()

    if core_tokens:
        core = " ".join(core_tokens)
        if core not in queries:
            queries.append(core)

    return queries


def _strip_trailing_punctuation(token: str) -> str:
    """Drop common sentence-ending punctuation from a token."""
    return token.rstrip(_TRAILING_PUNCTUATION)


def _split_hangul_compound_token(token: str) -> str:
    """Generically split simple 4-syllable Hangul compounds into 2+2 chunks.

    This avoids domain-specific token maps while still helping common compounds
    like `채용공고`, `공개채용`, `채용안내` match spaced titles.
    """
    if _HANGUL_COMPOUND_RE.match(token):
        return f"{token[:2]} {token[2:]}"
    return token


def _build_bm25_query(query: str) -> str:
    """Build a compact raw-text lexical query without Kiwi-specific preprocessing."""
    tokens = [_strip_trailing_punctuation(token) for token in query.split()]
    stripped_tokens = [strip_particles(token) for token in tokens if token]
    normalized = [token for token in stripped_tokens if token]
    return " ".join(normalized) or query.strip()


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
