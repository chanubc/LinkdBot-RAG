"""Phase 3: ChunkRepository FTS regression tests.

Verifies that save_chunks and search_similar keep the pre-Kiwi Phase 3 SQL
shape: `tsv`/FTS stays enabled, but raw content/query text is used directly.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.repository.chunk_repository import ChunkRepository


def make_repo() -> tuple[ChunkRepository, AsyncMock]:
    """Return a ChunkRepository with a mocked AsyncSession."""
    db = AsyncMock()
    db.execute = AsyncMock()
    repo = ChunkRepository(db)
    return repo, db


@pytest.mark.asyncio
async def test_save_chunks_uses_raw_content_for_tsvector():
    """save_chunks should pass raw content directly to to_tsvector()."""
    repo, db = make_repo()
    fake_embedding = [0.1] * 1536
    original_content = "채용공고 안내문"

    await repo.save_chunks(
        link_id=1,
        chunks=[(original_content, fake_embedding)],
    )

    execute_call = db.execute.call_args
    params_list = execute_call[0][1]
    assert isinstance(params_list, list) and len(params_list) == 1
    params = params_list[0]

    assert "content" in params
    assert params["content"] == original_content
    assert "morpheme_content" not in params


@pytest.mark.asyncio
async def test_search_similar_uses_raw_query_text_for_fts():
    """search_similar should pass raw query_text directly to plainto_tsquery()."""
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    query_text = "채용공고를"

    await repo.search_similar(
        user_id=1,
        query_embedding=[0.1] * 1536,
        top_k=5,
        query_text=query_text,
    )

    execute_call = db.execute.call_args
    params = execute_call[0][1]

    assert "query_text" in params
    assert params["query_text"] == query_text
    assert "morpheme_query" not in params


@pytest.mark.asyncio
async def test_search_similar_dense_only_keeps_query_param_absent():
    """Dense-only path should not send an FTS query parameter."""
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    await repo.search_similar(
        user_id=1,
        query_embedding=[0.1] * 1536,
        top_k=5,
        query_text="",
    )

    execute_call = db.execute.call_args
    params = execute_call[0][1]

    assert "query_text" not in params
    assert "morpheme_query" not in params


@pytest.mark.asyncio
async def test_search_similar_sql_keeps_phase3_hybrid_shape():
    """Hybrid SQL should still contain FTS and dense+sparse merge primitives."""
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    await repo.search_similar(
        user_id=1,
        query_embedding=[0.1] * 1536,
        top_k=5,
        query_text="채용공고",
    )

    sql_text = str(db.execute.call_args[0][0])
    assert "ts_rank" in sql_text
    assert "plainto_tsquery('simple', :query_text)" in sql_text
    assert "c.tsv @@" in sql_text
    assert "d.dense_score * 0.7 + COALESCE(s.sparse_score, 0) * 0.3" in sql_text


@pytest.mark.asyncio
async def test_search_bm25_uses_raw_non_kiwi_query_text():
    """BM25 fallback should send the normalized raw query text unchanged to SQL."""
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    await repo.search_bm25(
        user_id=1,
        query_text="채용공고 링크",
        top_k=10,
    )

    execute_call = db.execute.call_args
    params = execute_call[0][1]

    assert params["query_text"] == "채용공고 링크"
    assert "morpheme_query" not in params


@pytest.mark.asyncio
async def test_search_bm25_sql_keeps_raw_text_rank_path():
    """BM25 fallback SQL should keep the precomputed chunk tsv path and safe tsquery."""
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    await repo.search_bm25(
        user_id=1,
        query_text="채용공고 링크",
        top_k=10,
    )

    sql_text = str(db.execute.call_args[0][0])
    assert "ts_rank_cd" in sql_text
    assert "plainto_tsquery('simple', :query_text)" in sql_text
    assert "replace(:query_text, ' ', '')" in sql_text
    assert "c.tsv @@ query.q" in sql_text
    assert "DISTINCT ON (l.id)" in sql_text
    assert "replace(COALESCE(l.title, ''), ' ', '')" in sql_text
    assert "morpheme" not in sql_text.lower()


@pytest.mark.asyncio
async def test_search_bm25_og_candidates_do_not_require_summary_embedding():
    repo, db = make_repo()
    mock_result = MagicMock()
    mock_result.mappings.return_value = []
    db.execute.return_value = mock_result

    await repo.search_bm25(
        user_id=1,
        query_text="AI 관련 자료",
        top_k=10,
    )

    sql_text = str(db.execute.call_args[0][0])
    assert "summary_embedding IS NOT NULL" not in sql_text
