"""summary_embedding + tsvector 백필 스크립트.

최근 30일 링크 중 summary_embedding이 None인 링크를 일괄 재처리하고,
tsv(Full-Text Search 벡터)가 NULL인 chunks를 배치 업데이트한다.

Usage:
    python -m scripts.backfill_summary_embeddings
"""
import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger
from sqlalchemy import text

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.llm.openai_client import OpenAIRepository

BATCH_SIZE = 20
TSV_BATCH_SIZE = 100
LOOKBACK_DAYS = 30


async def backfill_summary_embeddings() -> None:
    """summary_embedding이 NULL인 링크를 배치로 임베딩 생성 후 저장."""
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
        logger.info("summary_embedding 백필 대상 링크 없음")
        return

    logger.info(f"summary_embedding 백필 대상: {len(rows)}개")

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        ids = [row.id for row in batch]
        summaries = [row.summary for row in batch]

        try:
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
                f"summary_embedding 배치 완료: {batch_start + 1}–{batch_start + len(batch)} / {len(rows)}"
            )
        except Exception:
            logger.exception(
                f"summary_embedding 배치 실패: {batch_start + 1}–{batch_start + len(batch)}, 다음 배치 계속"
            )

    logger.info(f"summary_embedding 백필 완료: 총 {len(rows)}개 처리")


async def backfill_tsv_chunks() -> None:
    """tsv(tsvector)가 NULL인 chunks를 배치로 to_tsvector 업데이트."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT id FROM chunks WHERE tsv IS NULL ORDER BY id")
        )
        ids = [row.id for row in result.fetchall()]

    if not ids:
        logger.info("tsvector 백필 대상 chunk 없음")
        return

    logger.info(f"tsvector 백필 대상: {len(ids)}개")

    for batch_start in range(0, len(ids), TSV_BATCH_SIZE):
        batch_ids = ids[batch_start : batch_start + TSV_BATCH_SIZE]
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text(
                        "UPDATE chunks SET tsv = to_tsvector('simple', content)"
                        " WHERE id = ANY(:ids)"
                    ),
                    {"ids": batch_ids},
                )
                await session.commit()

            logger.info(
                f"tsvector 배치 완료: {batch_start + 1}–{batch_start + len(batch_ids)} / {len(ids)}"
            )
        except Exception:
            logger.exception(
                f"tsvector 배치 실패: {batch_start + 1}–{batch_start + len(batch_ids)}, 다음 배치 계속"
            )

    logger.info(f"tsvector 백필 완료: 총 {len(ids)}개 처리")


async def main() -> None:
    logger.info("=== 백필 시작 ===")
    await backfill_summary_embeddings()
    await backfill_tsv_chunks()
    logger.info("=== 백필 완료 ===")


if __name__ == "__main__":
    asyncio.run(main())
