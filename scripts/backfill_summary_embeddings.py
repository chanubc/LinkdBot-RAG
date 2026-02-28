"""summary_embedding 백필 스크립트.

최근 30일 링크 중 summary_embedding이 None인 링크를 일괄 재처리한다.

Usage:
    python -m scripts.backfill_summary_embeddings
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.llm.openai_client import OpenAIRepository

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 20
LOOKBACK_DAYS = 30


async def main() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    openai = OpenAIRepository()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                """
                SELECT id, summary
                FROM links
                WHERE summary_embedding IS NULL
                  AND summary IS NOT NULL
                  AND created_at >= :cutoff
                ORDER BY id
                """
            ),
            {"cutoff": cutoff},
        )
        rows = result.fetchall()

    if not rows:
        logger.info("백필 대상 링크 없음")
        return

    logger.info("백필 대상: %d개", len(rows))

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        ids = [row.id for row in batch]
        summaries = [row.summary for row in batch]

        embeddings = await openai.embed(summaries)

        async with AsyncSessionLocal() as session:
            for link_id, embedding in zip(ids, embeddings):
                await session.execute(
                    text(
                        "UPDATE links SET summary_embedding = CAST(:emb AS vector) WHERE id = :id"
                    ),
                    {"emb": str(embedding), "id": link_id},
                )
            await session.commit()

        logger.info(
            "배치 완료: %d–%d / %d",
            batch_start + 1,
            batch_start + len(batch),
            len(rows),
        )

    logger.info("백필 완료: 총 %d개 처리", len(rows))


if __name__ == "__main__":
    asyncio.run(main())
