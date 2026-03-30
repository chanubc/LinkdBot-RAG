"""Profile HybridRetriever latency for representative queries.

Default mode uses a lightweight mock retriever so the script can run without
DB/OpenAI credentials. Use ``--real --user <telegram_user_id>`` to benchmark
the actual repository path.
"""

from __future__ import annotations

import argparse
import asyncio
import pathlib
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.application.services.search_query_builder import build_search_queries
from app.infrastructure.rag.retriever import (
    HybridRetriever,
    _apply_score_cutoff,
    _build_bm25_query,
    _dedupe_by_link,
    _merge_query_batches,
    _merge_results,
    _rescore_with_keywords,
)

DEFAULT_QUERIES = [
    "하나 증권 채용",
    "채용공고 링크 가져와",
    "스타트업 취업 전략",
]


class MockOpenAI:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 5 for _ in texts]


class MockChunkRepository:
    async def search_og_links(self, user_id: int, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        return []

    async def search_similar(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        query_texts: list[str] | None = None,
    ) -> list[dict]:
        results = []
        for priority, query_text in enumerate(query_texts or [], start=1):
            results.append(
                {
                    "link_id": priority,
                    "title": f"{query_text} 관련 문서",
                    "url": f"https://example.com/{priority}",
                    "summary": "",
                    "category": "General",
                    "keywords": "[]",
                    "content_source": "jina",
                    "chunk_content": query_text,
                    "dense_score": max(0.2, 0.8 - priority * 0.05),
                    "similarity": max(0.2, 0.8 - priority * 0.05),
                    "query_priority": priority,
                }
            )
        return results

    async def search_bm25(
        self,
        user_id: int,
        query_texts: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        results = []
        for priority, query_text in enumerate(query_texts, start=1):
            results.append(
                {
                    "link_id": 100 + priority,
                    "title": f"{query_text} 키워드 매치",
                    "url": f"https://example.com/bm25/{priority}",
                    "summary": "",
                    "category": "General",
                    "keywords": '["채용공고", "링크", "스타트업", "취업"]',
                    "content_source": "jina",
                    "chunk_content": query_text,
                    "dense_score": 0.0,
                    "similarity": max(0.25, 0.7 - priority * 0.04),
                    "bm25_score": max(0.25, 0.7 - priority * 0.04),
                    "query_priority": priority,
                }
            )
        return results


class LegacyMockChunkRepository:
    async def search_og_links(self, user_id: int, query_embedding: list[float], top_k: int = 5) -> list[dict]:
        return []

    async def search_similar(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        query_text: str = "",
    ) -> list[dict]:
        if not query_text.strip():
            return []
        return [
            {
                "link_id": 1,
                "title": f"{query_text} 관련 문서",
                "url": "https://example.com/legacy/1",
                "summary": "",
                "category": "General",
                "keywords": "[]",
                "content_source": "jina",
                "chunk_content": query_text,
                "dense_score": 0.72,
                "similarity": 0.72,
            }
        ]

    async def search_bm25(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
    ) -> list[dict]:
        if not query_text.strip():
            return []
        return [
            {
                "link_id": 100,
                "title": f"{query_text} 키워드 매치",
                "url": "https://example.com/legacy/bm25",
                "summary": "",
                "category": "General",
                "keywords": '["채용공고", "링크", "스타트업", "취업"]',
                "content_source": "jina",
                "chunk_content": query_text,
                "dense_score": 0.0,
                "similarity": 0.68,
                "bm25_score": 0.68,
            }
        ]


async def _build_real_retriever() -> tuple[HybridRetriever, object]:
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.llm.openai_client import OpenAIRepository
    from app.infrastructure.repository.chunk_repository import ChunkRepository

    session = AsyncSessionLocal()
    retriever = HybridRetriever(OpenAIRepository(), ChunkRepository(session))
    return retriever, session


async def _build_mock_retriever() -> tuple[HybridRetriever, None]:
    return HybridRetriever(MockOpenAI(), MockChunkRepository()), None


async def _legacy_mock_retrieve(query: str, top_k: int = 5) -> list[dict]:
    openai = MockOpenAI()
    chunk_repo = LegacyMockChunkRepository()
    [embedding] = await openai.embed([query])
    og_results = await chunk_repo.search_og_links(user_id=1, query_embedding=embedding, top_k=max(top_k * 5, 30))

    merged_across_queries: list[dict] = []
    seen_queries: set[str] = set()
    for query_index, query_text in enumerate(build_search_queries(query)):
        candidate = query_text.strip()
        if not candidate or candidate in seen_queries:
            continue
        seen_queries.add(candidate)

        chunk_results = await chunk_repo.search_similar(1, embedding, max(top_k * 5, 30), candidate)
        bm25_results = await chunk_repo.search_bm25(1, _build_bm25_query(candidate), max(top_k * 2, 10))
        merged = _merge_results(chunk_results, og_results, bm25_results)
        rescored = _rescore_with_keywords(merged, candidate)
        deduped = _apply_score_cutoff(_dedupe_by_link(rescored))
        merged_across_queries = _merge_query_batches(
            merged_across_queries,
            deduped,
            query_index=query_index,
        )
        if len(merged_across_queries) >= top_k:
            break

    return merged_across_queries[:top_k]


async def _run_profile(queries: list[str], repeats: int, real: bool, user_id: int | None) -> None:
    if real:
        if user_id is None:
            raise SystemExit("--real mode requires --user <id>")
        retriever, session = await _build_real_retriever()
    else:
        user_id = user_id or 1
        retriever, session = await _build_mock_retriever()

    try:
        print(f"mode={'real' if real else 'mock'} repeats={repeats} user_id={user_id}")
        for query in queries:
            latencies_ms: list[float] = []
            legacy_latencies_ms: list[float] = []
            result_count = 0
            for _ in range(repeats):
                started = time.perf_counter()
                results = await retriever.retrieve(user_id=user_id, query=query, top_k=5)
                elapsed_ms = (time.perf_counter() - started) * 1000
                latencies_ms.append(elapsed_ms)
                result_count = len(results)
                if not real:
                    legacy_started = time.perf_counter()
                    await _legacy_mock_retrieve(query, top_k=5)
                    legacy_latencies_ms.append((time.perf_counter() - legacy_started) * 1000)
            avg_ms = statistics.mean(latencies_ms)
            p95_ms = max(latencies_ms) if len(latencies_ms) < 20 else statistics.quantiles(latencies_ms, n=20)[18]
            print(
                f"- query={query!r} avg_ms={avg_ms:.2f} p95_ms={p95_ms:.2f} "
                f"min_ms={min(latencies_ms):.2f} max_ms={max(latencies_ms):.2f} results={result_count}"
            )
            if legacy_latencies_ms:
                legacy_avg = statistics.mean(legacy_latencies_ms)
                delta = legacy_avg - avg_ms
                print(
                    f"  legacy_mock_avg_ms={legacy_avg:.2f} consolidated_delta_ms={delta:.2f}"
                )
    finally:
        if session is not None:
            await session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile HybridRetriever latency.")
    parser.add_argument("--real", action="store_true", help="Measure the real DB/OpenAI-backed retriever.")
    parser.add_argument("--user", type=int, help="User id for --real mode.")
    parser.add_argument("--repeats", type=int, default=5, help="How many times to run each query.")
    parser.add_argument("--query", action="append", dest="queries", help="Override default representative query set.")
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    asyncio.run(_run_profile(queries, args.repeats, args.real, args.user))


if __name__ == "__main__":
    main()
