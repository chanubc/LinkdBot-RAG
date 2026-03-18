import json
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.rag.retriever import HybridRetriever


def make_retriever():
    openai = AsyncMock()
    openai.embed.return_value = [[0.1] * 5]
    chunk_repo = AsyncMock()
    chunk_repo.search_og_links.return_value = []
    chunk_repo.search_bm25.return_value = []
    return HybridRetriever(openai=openai, chunk_repo=chunk_repo), chunk_repo


def _make_result(link_id, title, keywords, dense_score, *, chunk_content="", similarity=None):
    return {
        "link_id": link_id,
        "title": title,
        "keywords": json.dumps(keywords),
        "dense_score": dense_score,
        "similarity": dense_score * 0.7 if similarity is None else similarity,
        "content_source": "jina",
        "url": f"https://example.com/{link_id}",
        "summary": "",
        "category": "Career",
        "chunk_content": chunk_content,
    }


@pytest.mark.asyncio
async def test_exact_chunk_phrase_outranks_generic_link_result_for_job_posting_query():
    """A BM25 hit should be able to upgrade an already-seen dense candidate."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(
            2,
            "일반 링크 정리",
            ["링크", "모음"],
            dense_score=0.72,
            chunk_content="여러 참고 링크를 정리한 문서",
        ),
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.50,
            chunk_content="지원 안내",
        ),
    ]
    chunk_repo.search_bm25.return_value = [
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.0,
            similarity=1.10,
            chunk_content="지원 안내: 채용공고 링크는 본문 하단에서 확인하세요.",
        ),
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고 링크", top_k=5)

    assert results[0]["link_id"] == 1


@pytest.mark.asyncio
async def test_link_phrase_breaks_tie_between_same_keyword_documents():
    """A stronger BM25 candidate should beat a denser summary-only result."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(
            2,
            "하나증권 채용 요약",
            ["하나증권", "채용공고"],
            dense_score=0.66,
            chunk_content="채용공고 핵심 요약과 전형 정리",
        ),
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.54,
            chunk_content="지원 안내",
        ),
    ]
    chunk_repo.search_bm25.return_value = [
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.0,
            similarity=1.05,
            chunk_content="원문 채용공고 링크와 지원 페이지를 함께 안내",
        ),
    ]

    results = await retriever.retrieve(user_id=111, query="하나증권 채용공고 링크", top_k=5)

    assert results[0]["link_id"] == 1


@pytest.mark.asyncio
async def test_bm25_duplicate_same_link_must_upgrade_existing_dense_hit():
    """A stronger BM25 duplicate should not be discarded during merge."""
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.50,
            chunk_content="지원 안내",
        ),
        _make_result(
            2,
            "일반 링크 정리",
            ["링크", "모음"],
            dense_score=0.72,
            chunk_content="여러 참고 링크를 정리한 문서",
        ),
    ]
    chunk_repo.search_bm25.return_value = [
        _make_result(
            1,
            "하나증권 2026 신입사원 공개채용",
            ["하나증권", "채용공고"],
            dense_score=0.0,
            similarity=1.10,
            chunk_content="지원 안내: 채용공고 링크는 본문 하단에서 확인하세요.",
        ),
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고 링크", top_k=5)

    assert results[0]["link_id"] == 1
