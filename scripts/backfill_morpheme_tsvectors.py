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
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()

_BATCH_SIZE = 500
_SUPPORTED_SCHEMES = ("postgresql://", "postgresql+", "postgres://")


def _build_async_url(database_url: str) -> object:
    """Normalize DATABASE_URL to postgresql+asyncpg. Raises on unsupported schemes."""
    if not any(database_url.startswith(s) for s in _SUPPORTED_SCHEMES):
        scheme = database_url.split("://")[0] if "://" in database_url else database_url[:20]
        raise RuntimeError(
            f"Unsupported DATABASE_URL scheme: {scheme!r}. "
            f"Expected postgresql://, postgresql+<driver>://, or postgres://"
        )
    return make_url(database_url).set(drivername="postgresql+asyncpg")


def _make_kiwi():
    """Load kiwipiepy or fail immediately — no silent fallback in backfill context."""
    try:
        from kiwipiepy import Kiwi  # type: ignore[import]
    except ImportError:
        raise RuntimeError("kiwipiepy is required: pip install kiwipiepy")
    return Kiwi()


def _strict_tokenize(kiwi, text: str) -> str:
    """Tokenize without fallback. Any exception propagates to abort the backfill."""
    tokens = kiwi.tokenize(text or "")
    return " ".join(t.form for t in tokens if t.tag.startswith(("NN", "VV", "SL", "XR")))


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    url = _build_async_url(database_url)
    kiwi = _make_kiwi()  # fail-fast: abort if kiwipiepy unavailable
    engine = create_async_engine(url)

    try:
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
                    {"mc": _strict_tokenize(kiwi, row.content or ""), "id": row.id}
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
    finally:
        await engine.dispose()

    print(f"Done. {updated} chunks updated.")


if __name__ == "__main__":
    asyncio.run(main())
