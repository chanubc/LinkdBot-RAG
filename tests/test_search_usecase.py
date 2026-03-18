from unittest.mock import AsyncMock

import pytest

from app.application.usecases.search_usecase import SearchUseCase
from app.infrastructure.rag.reranker import SimpleReranker


def _make_result(link_id: int, title: str, similarity: float) -> dict:
    return {
        "link_id": link_id,
        "title": title,
        "url": f"https://example.com/{link_id}",
        "similarity": similarity,
    }


@pytest.mark.asyncio
async def test_search_usecase_tries_normalized_queries_when_results_are_sparse():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [
        _make_result(1, "하나증권 2026 신입사원 공개채용", 0.57),
        _make_result(2, "롯데이노베이트 2026 신입사원 채용 공고", 0.51),
        _make_result(3, "아이샵케어 채용 안내", 0.49),
        _make_result(4, "2026 삼성그룹 채용 핵심 가이드", 0.40),
        _make_result(5, "NH투자증권 2026년 신입사원 공채", 0.39),
    ]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    results = await usecase.execute(111, "채용공고 링크 가져와", top_k=5)

    retriever.retrieve.assert_awaited_once_with(
        111,
        "채용공고 링크 가져와",
        10,
        search_queries=["채용공고 링크 가져와", "채용공고"],
    )
    assert [r["link_id"] for r in results] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_search_usecase_builds_progressive_query_family_for_spaced_query():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [
        _make_result(1, "A", 0.9),
        _make_result(2, "B", 0.8),
        _make_result(3, "C", 0.7),
        _make_result(4, "D", 0.6),
        _make_result(5, "E", 0.5),
    ]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    results = await usecase.execute(111, "롯데 채용 공고", top_k=5)

    retriever.retrieve.assert_awaited_once_with(
        111,
        "롯데 채용 공고",
        10,
        search_queries=["롯데 채용 공고", "롯데 채용", "롯데"],
    )
    assert [r["link_id"] for r in results] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_search_usecase_preserves_retriever_ranked_results():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [
        _make_result(1, "A", 0.55),
        _make_result(2, "B", 0.50),
    ]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    results = await usecase.execute(111, "채용공고 링크", top_k=5)

    assert [r["link_id"] for r in results] == [1, 2]
    assert results[0]["similarity"] == 0.55

    retriever.retrieve.assert_awaited_once_with(
        111,
        "채용공고 링크",
        10,
        search_queries=["채용공고 링크", "채용공고"],
    )


@pytest.mark.asyncio
async def test_search_usecase_builds_general_ai_query_family():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [_make_result(1, "AI 자료", 0.7)]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    await usecase.execute(111, "AI 관련 자료 알려줘", top_k=5)

    retriever.retrieve.assert_awaited_once_with(
        111,
        "AI 관련 자료 알려줘",
        10,
        search_queries=["AI 관련 자료 알려줘", "AI"],
    )


@pytest.mark.asyncio
async def test_search_usecase_builds_general_python_query_family():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [_make_result(1, "파이썬 비동기", 0.7)]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    await usecase.execute(111, "파이썬 비동기 자료 보여줘", top_k=5)

    retriever.retrieve.assert_awaited_once_with(
        111,
        "파이썬 비동기 자료 보여줘",
        10,
        search_queries=["파이썬 비동기 자료 보여줘", "파이썬 비동기", "파이썬"],
    )


@pytest.mark.asyncio
async def test_search_usecase_builds_progressive_query_family_for_general_topic():
    retriever = AsyncMock()
    retriever.retrieve.return_value = [_make_result(1, "스타트업 취업", 0.7)]
    usecase = SearchUseCase(retriever=retriever, reranker=SimpleReranker())

    await usecase.execute(111, "스타트업 취업 전략", top_k=5)

    retriever.retrieve.assert_awaited_once_with(
        111,
        "스타트업 취업 전략",
        10,
        search_queries=["스타트업 취업 전략", "스타트업 취업", "스타트업"],
    )
