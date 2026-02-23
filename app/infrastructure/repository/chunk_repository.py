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
        """청크 + 임베딩 벡터 저장."""
        for content, embedding in chunks:
            self._db.add(Chunk(link_id=link_id, content=content, embedding=embedding))

    async def search_similar(
        self,
        user_id: int,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """pgvector 코사인 유사도 검색."""
        emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
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
