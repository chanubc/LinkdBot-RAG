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


def _make_result(link_id, title, keywords, dense_score, *, similarity=None, content_source="jina", chunk_content=""):
    return {
        "link_id": link_id,
        "title": title,
        "keywords": json.dumps(keywords),
        "dense_score": dense_score,
        "similarity": dense_score * 0.7 if similarity is None else similarity,
        "content_source": content_source,
        "url": f"https://example.com/{link_id}",
        "summary": "",
        "category": "Career",
        "chunk_content": chunk_content,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["채용공고 링크", "채용공고 링크 가져와"])
async def test_non_kiwi_sparse_path_recovers_job_posting_link_canaries(query: str):
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(2, "일반 링크 정리", ["링크", "모음"], dense_score=0.72),
    ]
    chunk_repo.search_bm25.return_value = [
        {
            **_make_result(
                1,
                "하나증권 채용공고 링크 모음",
                ["하나증권", "채용공고", "링크"],
                dense_score=0.0,
                similarity=0.92,
                chunk_content="원문 채용공고 링크와 지원 페이지를 함께 안내",
            ),
            "bm25_score": 0.92,
        },
    ]

    results = await retriever.retrieve(user_id=111, query=query, top_k=3)

    assert results[0]["link_id"] == 1
    assert [call.args[1] for call in chunk_repo.search_bm25.await_args_list] == [
        query,
        "채용공고",
        "채용 공고",
    ]


@pytest.mark.asyncio
async def test_non_kiwi_sparse_path_does_not_duplicate_existing_dense_link():
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "하나증권 채용공고 링크 모음", ["하나증권", "채용공고", "링크"], dense_score=0.61),
        _make_result(2, "일반 링크 정리", ["링크", "모음"], dense_score=0.58),
    ]
    chunk_repo.search_bm25.return_value = [
        {
            **_make_result(
                1,
                "하나증권 채용공고 링크 모음",
                ["하나증권", "채용공고", "링크"],
                dense_score=0.0,
                similarity=0.95,
                chunk_content="원문 채용공고 링크와 지원 페이지를 함께 안내",
            ),
            "bm25_score": 0.95,
        },
    ]

    results = await retriever.retrieve(user_id=111, query="채용공고 링크", top_k=3)

    assert [r["link_id"] for r in results].count(1) == 1
    assert results[0]["link_id"] == 1


@pytest.mark.asyncio
async def test_non_kiwi_sparse_path_does_not_regress_lotte_job_posting_query():
    retriever, chunk_repo = make_retriever()
    chunk_repo.search_similar.return_value = [
        _make_result(1, "롯데이노베이트 채용공고", ["채용공고", "신입", "공고"], dense_score=0.50),
        _make_result(2, "하나증권 채용공고", ["하나증권", "채용공고"], dense_score=0.60),
    ]
    chunk_repo.search_bm25.return_value = [
        {
            **_make_result(3, "무관한 링크 모음", ["링크", "모음"], dense_score=0.0, similarity=0.34),
            "bm25_score": 0.34,
        },
    ]

    results = await retriever.retrieve(user_id=111, query="롯데 채용 공고", top_k=5)

    assert results[0]["link_id"] == 1
    assert 3 not in [r["link_id"] for r in results], "noisy sparse-only link should be cut off"
