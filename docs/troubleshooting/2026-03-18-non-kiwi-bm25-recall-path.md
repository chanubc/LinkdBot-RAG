# Non-Kiwi BM25-style sparse recall path

## Why this exists

Kiwi rollback restored the pre-PR95 `simple`-FTS pipeline, but that also removed the
extra Korean morpheme recall we had briefly relied on. Dense recall + keyword/title
rescoring still handles many cases, yet lexical intent-heavy queries such as
`채용공고 링크` can under-rank the right link when the dense candidate set is noisy.

This patch adds a **non-Kiwi sparse recall path** that keeps the existing
`chunks.tsv` index and does not introduce a new dependency.

## Design

1. `HybridRetriever.retrieve()` still fetches the dense hybrid chunk path and OG path.
2. It now also calls `ChunkRepository.search_bm25()` for the lexical path.
3. Search-driven fallback queries are built in a shared search-query builder (not the router), so `/search`, natural-language search, and direct `HybridRetriever` callers all reuse the same rewrite behavior. The fallback family now supports both tail trimming (for example `채용공고 링크 가져와` → `채용공고`) and progressive broadening (for example `스타트업 취업 전략` → `스타트업 취업` → `스타트업`).
4. `HybridRetriever` computes the embedding **once** for the original query, runs DB paths sequentially on the shared repository session, and keeps exact-query results ahead of broader fallback-only additions so widened recall does not outrank the user's original intent.
5. `search_bm25()`:
   - reuses the existing `chunks.tsv` index for the chunk-content path
   - adds a compact no-space title/summary lexical fallback so `채용공고` can still match `채용 공고`
   - ranks chunk hits with weighted title/summary + `c.tsv`
   - uses `plainto_tsquery('simple', ...)` for a safer raw-user-text path
   - collapses chunk hits per `link_id` before applying the recall limit
   - allows OG lexical candidates even when they do not have `summary_embedding`
   - returns lexical candidates for the normal Python rescoring/dedupe flow

So the retrieval stack is now:

- dense + FTS hybrid chunk path
- **non-Kiwi BM25-style lexical recall path**
- OG summary embedding path
- keyword/title overlap rescoring
- link-level dedupe + score cutoff

## Why this is safe

- No new dependency
- No schema migration
- No Kiwi-specific tokenization
- Reuses the existing `chunks.tsv` index for chunk-backed lexical recall while keeping OG lexical recall scoped to a smaller inline title/summary path
- Keeps query rewriting below the router, so search behavior stays consistent across search entry points
- Avoids concurrent use of the same SQLAlchemy `AsyncSession`

## Expected effect

- Better recall for lexical Korean queries where the right document is present in `chunks.tsv`
- Better ranking for exact-intent queries like `채용공고 링크`
- Existing particle/substring keyword logic still handles compound/attached-token cases

## Verification checklist

Run:

```bash
pytest tests/test_chunk_repository_fts.py tests/test_retriever.py
pytest tests/test_retriever_quality.py
```

Look for:

- sparse lexical SQL shape coverage
- retriever regression for the new BM25-style path
- no ranking regression for the existing OG/dense scenarios
