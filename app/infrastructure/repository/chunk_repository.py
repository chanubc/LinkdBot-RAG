from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.models.chunk import Chunk


class ChunkRepository(IChunkRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_chunks(
        self,
        link_id: int,
        chunks: list[tuple[str, list[float]]],
    ) -> None:
        """청크 + 임베딩 벡터 저장. tsvector도 함께 생성."""
        if not chunks:
            return
        # tsvector는 raw SQL로 생성 (ORM이 TSVECTOR 함수 호출 미지원)
        # SQL 객체 1회 생성 + executemany로 배치 처리 (DB round-trip 최소화)
        sql = text("""
            INSERT INTO chunks (link_id, content, embedding, tsv)
            VALUES (
                :link_id,
                :content,
                CAST(:emb AS vector),
                to_tsvector('simple', :content)
            )
        """)
        params = [
            {
                "link_id": link_id,
                "content": content,
                "emb": "[" + ",".join(str(v) for v in embedding) + "]",
            }
            for content, embedding in chunks
        ]
        await self._db.execute(sql, params)

    async def search_similar(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
        query_text: str = "",
    ) -> list[dict]:
        """Hybrid 검색: Dense(pgvector) × 0.7 + Sparse(FTS) × 0.3.

        query_text가 비어있으면 Dense-only 검색으로 폴백.
        """
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        if query_text:
            sql = text("""
                WITH dense AS (
                    SELECT
                        c.id AS chunk_id,
                        l.id AS link_id,
                        l.title,
                        l.url,
                        l.summary,
                        l.category,
                        l.keywords,
                        c.content AS chunk_content,
                        1 - (c.embedding <=> CAST(:emb AS vector)) AS dense_score
                    FROM chunks c
                    JOIN links l ON c.link_id = l.id
                    WHERE l.user_id = :user_id
                ),
                sparse AS (
                    SELECT
                        c.id AS chunk_id,
                        ts_rank(c.tsv, plainto_tsquery('simple', :query_text)) AS sparse_score
                    FROM chunks c
                    JOIN links l ON c.link_id = l.id
                    WHERE l.user_id = :user_id
                      AND c.tsv IS NOT NULL
                      AND c.tsv @@ plainto_tsquery('simple', :query_text)
                )
                SELECT
                    d.link_id,
                    d.title,
                    d.url,
                    d.summary,
                    d.category,
                    d.keywords,
                    d.chunk_content,
                    (d.dense_score * 0.7 + COALESCE(s.sparse_score, 0) * 0.3) AS similarity
                FROM dense d
                LEFT JOIN sparse s ON d.chunk_id = s.chunk_id
                ORDER BY similarity DESC
                LIMIT :top_k
            """)
            result = await self._db.execute(
                sql,
                {"emb": emb_str, "user_id": user_id, "query_text": query_text, "top_k": top_k},
            )
        else:
            # Dense-only 폴백
            sql = text("""
                SELECT
                    l.id        AS link_id,
                    l.title,
                    l.url,
                    l.summary,
                    l.category,
                    l.keywords,
                    c.content   AS chunk_content,
                    1 - (c.embedding <=> CAST(:emb AS vector)) AS similarity
                FROM chunks c
                JOIN links l ON c.link_id = l.id
                WHERE l.user_id = :user_id
                ORDER BY c.embedding <=> CAST(:emb AS vector)
                LIMIT :top_k
            """)
            result = await self._db.execute(
                sql,
                {"emb": emb_str, "user_id": user_id, "top_k": top_k},
            )

        return [dict(row) for row in result.mappings()]
