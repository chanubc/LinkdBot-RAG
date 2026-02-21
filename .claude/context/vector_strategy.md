# 🔍 Vector Strategy

- Use pgvector with cosine similarity.
- Embed summary, not raw HTML.
- Normalize embeddings before storing.
- Filter by `user_id` before similarity search.
- Limit Top-K results to 5–20.
- Use IVFFlat index on `chunks.embedding` for performance.
