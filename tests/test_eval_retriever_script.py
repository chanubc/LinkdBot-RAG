import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _load_eval_retriever_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "eval_retriever.py"
    spec = importlib.util.spec_from_file_location("eval_retriever_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_evaluate_real_returns_cleanly_when_real_queries_missing(capsys):
    module = _load_eval_retriever_module()
    module.REAL_EVAL_QUERIES = []

    await module.evaluate_real(user_id=1)

    out = capsys.readouterr().out
    assert "REAL_EVAL_QUERIES" in out


@pytest.mark.asyncio
async def test_evaluate_real_uses_current_openai_and_query_texts_interfaces(capsys, monkeypatch):
    module = _load_eval_retriever_module()
    module.REAL_EVAL_QUERIES = [
        {"query": "채용공고 링크", "relevant_urls": ["https://example.com/1"]},
    ]

    captured = {}

    class FakeSession:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeChunkRepository:
        def __init__(self, session):
            self.session = session

        async def search_similar(self, user_id, embedding, top_k, query_texts=None):
            captured["user_id"] = user_id
            captured["query_texts"] = query_texts
            captured["top_k"] = top_k
            return [
                {
                    "url": "https://example.com/1",
                    "dense_score": 0.8,
                    "similarity": 0.8,
                    "keywords": "[]",
                    "content_source": "jina",
                    "link_id": 1,
                }
            ]

    class FakeOpenAIRepository:
        async def embed(self, texts):
            captured["embed_texts"] = texts
            return [[0.1] * 5]

    fake_retriever_mod = types.ModuleType("app.infrastructure.rag.retriever")
    fake_retriever_mod._RECALL_MULTIPLIER = 5
    fake_retriever_mod._MIN_RECALL_K = 30
    fake_retriever_mod._MAX_RECALL_K = 100
    fake_retriever_mod._rescore_with_keywords = lambda raw, query: raw
    fake_retriever_mod._dedupe_by_link = lambda raw: raw

    fake_asyncio_mod = types.ModuleType("sqlalchemy.ext.asyncio")
    fake_asyncio_mod.AsyncSession = object
    fake_asyncio_mod.create_async_engine = lambda *args, **kwargs: object()

    fake_orm_mod = types.ModuleType("sqlalchemy.orm")
    fake_orm_mod.sessionmaker = lambda *args, **kwargs: (lambda: FakeSession())

    fake_repo_mod = types.ModuleType("app.infrastructure.repository.chunk_repository")
    fake_repo_mod.ChunkRepository = FakeChunkRepository

    fake_llm_mod = types.ModuleType("app.infrastructure.llm.openai_client")
    fake_llm_mod.OpenAIRepository = FakeOpenAIRepository

    fake_config_mod = types.ModuleType("app.core.config")
    fake_config_mod.settings = types.SimpleNamespace(DATABASE_URL="postgresql+asyncpg://example")

    monkeypatch.setitem(sys.modules, "sqlalchemy.ext.asyncio", fake_asyncio_mod)
    monkeypatch.setitem(sys.modules, "sqlalchemy.orm", fake_orm_mod)
    monkeypatch.setitem(sys.modules, "app.infrastructure.rag.retriever", fake_retriever_mod)
    monkeypatch.setitem(sys.modules, "app.infrastructure.repository.chunk_repository", fake_repo_mod)
    monkeypatch.setitem(sys.modules, "app.infrastructure.llm.openai_client", fake_llm_mod)
    monkeypatch.setitem(sys.modules, "app.core.config", fake_config_mod)

    await module.evaluate_real(user_id=8362770686, k=5)

    out = capsys.readouterr().out
    assert "P@5" in out
    assert captured["embed_texts"] == ["채용공고 링크"]
    assert captured["user_id"] == 8362770686
    assert captured["query_texts"] == ["채용공고 링크"]
