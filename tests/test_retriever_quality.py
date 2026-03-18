"""Retrieval quality benchmark for HybridRetriever.

Measures the impact of adding the OG summary_embedding search path
(search_og_links) alongside the existing chunk path (search_similar).

Metrics used:
  - precision@K  : fraction of top-K results that are relevant
  - recall@K     : fraction of relevant items found in top-K
  - MRR          : mean reciprocal rank (position of first relevant hit)
"""

import json
import pytest
from unittest.mock import AsyncMock

from app.infrastructure.rag.retriever import HybridRetriever


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def precision_at_k(results: list[dict], relevant_ids: set[int], k: int) -> float:
    top_k = [r["link_id"] for r in results[:k]]
    return sum(1 for lid in top_k if lid in relevant_ids) / max(k, 1)


def recall_at_k(results: list[dict], relevant_ids: set[int], k: int) -> float:
    top_k = [r["link_id"] for r in results[:k]]
    return sum(1 for lid in top_k if lid in relevant_ids) / max(len(relevant_ids), 1)


def mrr(results: list[dict], relevant_ids: set[int]) -> float:
    for i, r in enumerate(results, 1):
        if r["link_id"] in relevant_ids:
            return 1.0 / i
    return 0.0


# ---------------------------------------------------------------------------
# Corpus factory — matches _make_result pattern from test_retriever.py
# ---------------------------------------------------------------------------

def _make_result(
    link_id: int,
    title: str,
    keywords: list[str],
    dense_score: float,
    content_source: str = "jina",
) -> dict:
    return {
        "link_id": link_id,
        "title": title,
        "keywords": json.dumps(keywords),
        "dense_score": dense_score,
        "similarity": dense_score * 0.7,
        "content_source": content_source,
        "url": f"https://example.com/{link_id}",
        "summary": "",
        "category": "General",
        "chunk_content": "",
    }


# ---------------------------------------------------------------------------
# Retriever factories
# ---------------------------------------------------------------------------

def make_retriever() -> tuple[HybridRetriever, AsyncMock]:
    openai = AsyncMock()
    openai.embed.return_value = [[0.1] * 5]
    chunk_repo = AsyncMock()
    chunk_repo.search_bm25.return_value = []
    return HybridRetriever(openai=openai, chunk_repo=chunk_repo), chunk_repo


def make_retriever_chunk_only() -> tuple[HybridRetriever, AsyncMock]:
    """Returns a retriever where search_og_links always returns [].

    Simulates the *before* state — chunk path only, no OG summary_embedding.
    """
    openai = AsyncMock()
    openai.embed.return_value = [[0.1] * 5]
    chunk_repo = AsyncMock()
    chunk_repo.search_og_links.return_value = []
    chunk_repo.search_bm25.return_value = []
    return HybridRetriever(openai=openai, chunk_repo=chunk_repo), chunk_repo


# ---------------------------------------------------------------------------
# Scenario 1 — OG link recall improvement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario1_og_link_recall_improvement():
    """OG 링크가 chunk 경로에 없을 때 summary_embedding 경로로 recall이 개선된다.

    Before (chunk-only): 채용 관련 OG 링크가 chunk가 없으므로 recall=0.
    After  (chunk+OG)  : OG summary_embedding 경로로 해당 링크가 검색되어 recall>0.

    Corpus:
      - link 1,2,3 — AI/Python jina 링크 (dense 높음, 쿼리와 무관)
      - link 4,5   — 커리어/채용 OG 링크 (link 4 가 정답)
    Query: "하나증권 채용"
    Ground truth: {4}
    """
    # --- chunk 경로 corpus (jina 링크 3개, 쿼리와 무관) ---
    jina_corpus = [
        _make_result(1, "파이썬 비동기 프로그래밍", ["Python", "asyncio", "비동기", "개발"], dense_score=0.75),
        _make_result(2, "트랜스포머 아키텍처 완벽 정리", ["AI", "딥러닝", "트랜스포머", "NLP"], dense_score=0.72),
        _make_result(3, "FastAPI 실전 튜토리얼", ["FastAPI", "Python", "REST", "백엔드"], dense_score=0.70),
    ]

    # --- OG 경로 corpus (채용 OG 링크 2개) ---
    og_corpus = [
        _make_result(4, "하나증권 2026 신입 공채", ["하나증권", "채용공고", "신입사원", "금융"], dense_score=0.68, content_source="og"),
        _make_result(5, "삼성물산 경력 채용", ["삼성물산", "경력채용", "건설", "취업"], dense_score=0.55, content_source="og"),
    ]

    relevant_ids = {4}

    # --- Before: chunk-only retriever ---
    before_retriever, before_repo = make_retriever_chunk_only()
    before_repo.search_similar.return_value = jina_corpus
    before_results = await before_retriever.retrieve(user_id=1, query="하나증권 채용", top_k=5)

    before_recall = recall_at_k(before_results, relevant_ids, k=5)
    before_mrr = mrr(before_results, relevant_ids)

    # --- After: chunk+OG retriever ---
    after_retriever, after_repo = make_retriever()
    after_repo.search_similar.return_value = jina_corpus
    after_repo.search_og_links.return_value = og_corpus
    after_results = await after_retriever.retrieve(user_id=1, query="하나증권 채용", top_k=5)

    after_recall = recall_at_k(after_results, relevant_ids, k=5)
    after_mrr = mrr(after_results, relevant_ids)

    print(f"\n[Scenario 1] Before (chunk-only): recall@5={before_recall:.2f}, mrr={before_mrr:.2f}")
    print(f"[Scenario 1] After  (chunk+OG)  : recall@5={after_recall:.2f},  mrr={after_mrr:.2f}")

    # Before: OG 링크는 chunk 경로에 없으므로 recall=0
    assert before_recall == 0.0, "chunk-only 경로에서는 OG 링크가 검색되지 않아야 함"

    # After: OG 링크가 결과에 포함되어야 함
    after_link_ids = [r["link_id"] for r in after_results]
    assert 4 in after_link_ids, "하나증권 OG 링크(link_id=4)가 결과에 포함되어야 함"
    assert after_recall > 0.0, "OG 경로 추가 후 recall@5 > 0 이어야 함"
    assert after_mrr > 0.0, "OG 경로 추가 후 MRR > 0 이어야 함"


# ---------------------------------------------------------------------------
# Scenario 2 — Precision not degraded when OG links are unrelated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario2_precision_not_degraded_by_og_links():
    """OG 링크가 쿼리와 무관할 때 jina 링크들의 precision이 저하되지 않는다.

    OG summary_embedding 경로가 추가되었을 때, 관련 없는 OG 링크가
    상위 결과를 밀어내어 precision을 떨어뜨려서는 안 된다.

    Corpus:
      - link 1,2,3 — 파이썬 비동기 관련 jina 링크 (쿼리와 높은 관련성)
      - link 4,5   — 금융/채용 OG 링크 (쿼리와 무관)
    Query: "파이썬 비동기 개발"
    Ground truth: {1, 2, 3}
    """
    jina_corpus = [
        _make_result(1, "파이썬 asyncio 완전 정복", ["Python", "asyncio", "비동기", "이벤트루프", "개발"], dense_score=0.88),
        _make_result(2, "비동기 웹 크롤러 구현", ["Python", "비동기", "크롤링", "aiohttp", "개발"], dense_score=0.85),
        _make_result(3, "async/await 패턴 가이드", ["Python", "async", "await", "코루틴", "개발"], dense_score=0.82),
    ]

    og_corpus = [
        _make_result(4, "하나증권 투자 분석 리포트", ["하나증권", "주식", "금융", "투자"], dense_score=0.50, content_source="og"),
        _make_result(5, "부동산 경매 입문 가이드", ["부동산", "경매", "투자", "재테크"], dense_score=0.45, content_source="og"),
    ]

    relevant_ids = {1, 2, 3}

    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = jina_corpus
    chunk_repo.search_og_links.return_value = og_corpus

    results = await retriever.retrieve(user_id=1, query="파이썬 비동기 개발", top_k=5)

    prec3 = precision_at_k(results, relevant_ids, k=3)
    rec5 = recall_at_k(results, relevant_ids, k=5)
    m = mrr(results, relevant_ids)

    print(f"\n[Scenario 2] precision@3={prec3:.2f}, recall@5={rec5:.2f}, mrr={m:.2f}")

    # 상위 3개 중 최소 2개는 jina 링크여야 함 (precision >= 0.67)
    assert prec3 >= 0.67, f"precision@3={prec3:.2f} < 0.67: 관련 없는 OG 링크가 상위를 침범함"

    # 1위 결과는 jina 링크여야 함
    assert results[0]["link_id"] in relevant_ids, "최상위 결과는 관련 jina 링크여야 함"
    assert results[0]["content_source"] == "jina", "최상위 결과의 content_source는 'jina'여야 함"

    # MRR: 첫 번째 관련 결과가 매우 높은 순위여야 함
    assert m >= 0.5, f"mrr={m:.2f}: 관련 결과가 너무 낮은 순위에 있음"


# ---------------------------------------------------------------------------
# Scenario 3 — Mixed relevance: both jina and OG links are relevant
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario3_mixed_relevance_all_relevant_links_found():
    """jina 링크와 OG 링크 모두 관련 있을 때 전체 recall=1.0이 달성된다.

    chunk 경로와 OG 경로를 함께 사용하면 두 경로의 관련 링크를 모두 수집할 수 있다.

    Corpus:
      - link 1,2   — 스타트업 관련 jina 링크 (관련)
      - link 3     — 스타트업 채용 OG 링크 (관련)
      - link 4,5   — 무관한 링크 (jina 1개, OG 1개)
    Query: "스타트업 취업 전략"
    Ground truth: {1, 2, 3}
    """
    jina_corpus = [
        _make_result(1, "스타트업 합류 전 반드시 확인할 것", ["스타트업", "취업", "커리어", "이직", "전략"], dense_score=0.80),
        _make_result(2, "초기 스타트업 개발자 연봉 협상", ["스타트업", "개발자", "연봉", "취업", "협상"], dense_score=0.76),
        _make_result(4, "도커 컨테이너 운영 가이드", ["Docker", "컨테이너", "DevOps", "인프라"], dense_score=0.60),
    ]

    og_corpus = [
        _make_result(3, "카카오벤처스 포트폴리오 스타트업 채용", ["스타트업", "채용", "취업", "카카오벤처스"], dense_score=0.74, content_source="og"),
        _make_result(5, "2025년 부동산 시장 전망", ["부동산", "투자", "아파트", "시장"], dense_score=0.42, content_source="og"),
    ]

    relevant_ids = {1, 2, 3}

    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = jina_corpus
    chunk_repo.search_og_links.return_value = og_corpus

    results = await retriever.retrieve(user_id=1, query="스타트업 취업 전략", top_k=5)

    rec5 = recall_at_k(results, relevant_ids, k=5)
    prec5 = precision_at_k(results, relevant_ids, k=5)
    m = mrr(results, relevant_ids)

    print(f"\n[Scenario 3] recall@5={rec5:.2f}, precision@5={prec5:.2f}, mrr={m:.2f}")
    print(f"[Scenario 3] result link_ids={[r['link_id'] for r in results]}")

    # 3개 관련 링크가 모두 발견되어야 함
    result_ids = {r["link_id"] for r in results}
    assert 1 in result_ids, "jina 관련 링크(link_id=1)가 결과에 포함되어야 함"
    assert 2 in result_ids, "jina 관련 링크(link_id=2)가 결과에 포함되어야 함"
    assert 3 in result_ids, "OG 관련 링크(link_id=3)가 결과에 포함되어야 함"

    assert rec5 == 1.0, f"recall@5={rec5:.2f}: 3개 관련 링크 모두 발견되어야 함"
    assert len(results) >= 3, "결과 수는 최소 3개여야 함"
    assert m >= 0.5, f"mrr={m:.2f}: 첫 번째 관련 결과가 상위에 있어야 함"


# ---------------------------------------------------------------------------
# Scenario 3b — Chunk-only would miss the OG relevant link
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario3b_chunk_only_misses_og_relevant_link():
    """chunk-only 경로에서는 관련 OG 링크가 누락되어 recall<1.0이 된다.

    Scenario 3의 before/after 대비를 명시적으로 검증한다.
    """
    jina_corpus = [
        _make_result(1, "스타트업 합류 전 반드시 확인할 것", ["스타트업", "취업", "커리어", "이직", "전략"], dense_score=0.80),
        _make_result(2, "초기 스타트업 개발자 연봉 협상", ["스타트업", "개발자", "연봉", "취업", "협상"], dense_score=0.76),
        _make_result(4, "도커 컨테이너 운영 가이드", ["Docker", "컨테이너", "DevOps", "인프라"], dense_score=0.60),
    ]

    og_corpus = [
        _make_result(3, "카카오벤처스 포트폴리오 스타트업 채용", ["스타트업", "채용", "취업", "카카오벤처스"], dense_score=0.74, content_source="og"),
        _make_result(5, "2025년 부동산 시장 전망", ["부동산", "투자", "아파트", "시장"], dense_score=0.42, content_source="og"),
    ]

    relevant_ids = {1, 2, 3}

    # --- Before: chunk-only ---
    before_retriever, before_repo = make_retriever_chunk_only()
    before_repo.search_similar.return_value = jina_corpus
    before_results = await before_retriever.retrieve(user_id=1, query="스타트업 취업 전략", top_k=5)

    # --- After: chunk+OG ---
    after_retriever, after_repo = make_retriever()
    after_repo.search_similar.return_value = jina_corpus
    after_repo.search_og_links.return_value = og_corpus
    after_results = await after_retriever.retrieve(user_id=1, query="스타트업 취업 전략", top_k=5)

    before_recall = recall_at_k(before_results, relevant_ids, k=5)
    after_recall = recall_at_k(after_results, relevant_ids, k=5)

    print(f"\n[Scenario 3b] chunk-only recall@5={before_recall:.2f}")
    print(f"[Scenario 3b] chunk+OG  recall@5={after_recall:.2f}")

    # chunk-only는 OG 링크(link_id=3)를 놓쳐서 recall < 1.0
    assert before_recall < 1.0, "chunk-only에서는 OG 관련 링크가 누락되어 recall < 1.0이어야 함"
    assert 3 not in {r["link_id"] for r in before_results}, "chunk-only 결과에 OG 링크(link_id=3)가 없어야 함"

    # chunk+OG는 모든 관련 링크를 찾아 recall == 1.0
    assert after_recall == 1.0, "chunk+OG에서는 모든 관련 링크를 찾아 recall=1.0이어야 함"
