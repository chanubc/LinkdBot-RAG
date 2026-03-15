"""Backfill chunk tsvectors with kiwipiepy morpheme tokenization.

One-time script to rebuild existing chunks' tsv column using morpheme-split tokens.
New chunks are tokenized at insert time, so this only needs to run once on
servers that had chunks before Phase B was deployed.

Usage:
    python scripts/backfill_morpheme_tsvectors.py

Safe to run multiple times (idempotent).
"""

from __future__ import annotations

import asyncio
import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlalchemy as sa
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.rag.korean_utils import morpheme_tokenize

load_dotenv()

_BATCH_SIZE = 500


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    # Ensure asyncpg dialect
    if not database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(database_url)

    async with engine.connect() as conn:
        result = await conn.execute(sa.text("SELECT COUNT(*) FROM chunks"))
        total = result.scalar() or 0
        if total == 0:
            print("No chunks to backfill.")
            return

        print(f"Backfilling {total} chunks...")
        last_id = 0
        updated = 0

        while True:
            rows = (
                await conn.execute(
                    sa.text(
                        "SELECT id, content FROM chunks "
                        "WHERE id > :last_id ORDER BY id LIMIT :lim"
                    ),
                    {"last_id": last_id, "lim": _BATCH_SIZE},
                )
            ).fetchall()

            if not rows:
                break

            params = [
                {"mc": morpheme_tokenize(row.content or ""), "id": row.id}
                for row in rows
            ]
            await conn.execute(
                sa.text("UPDATE chunks SET tsv = to_tsvector('simple', :mc) WHERE id = :id"),
                params,
            )
            await conn.commit()

            updated += len(rows)
            last_id = rows[-1].id
            print(f"  {updated}/{total} done...")

        await conn.execute(sa.text("ANALYZE chunks"))
        await conn.commit()

    await engine.dispose()
    print(f"Done. {updated} chunks updated.")


if __name__ == "__main__":
    asyncio.run(main())
