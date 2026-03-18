"""Rebuild chunk tsvectors without Kiwi tokenization.

One-time recovery script for rolling back PR #95 Kiwi Phase B behavior.
It regenerates `chunks.tsv` from raw `content` using PostgreSQL's `simple`
dictionary so runtime code and indexed data share the same semantics again.

Usage:
    python scripts/rebuild_tsvectors_without_kiwi.py
    python scripts/rebuild_tsvectors_without_kiwi.py --dry-run
    python scripts/rebuild_tsvectors_without_kiwi.py --batch-size 1000
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_BATCH_SIZE = 500
SUPPORTED_SCHEMES = ("postgresql://", "postgresql+", "postgres://")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count affected rows without updating chunks.tsv",
    )
    return parser.parse_args()


def build_async_url(database_url: str) -> object:
    """Normalize DATABASE_URL to postgresql+asyncpg. Raises on unsupported schemes."""
    from sqlalchemy.engine import make_url

    if not any(database_url.startswith(s) for s in SUPPORTED_SCHEMES):
        scheme = database_url.split("://")[0] if "://" in database_url else database_url[:20]
        raise RuntimeError(
            f"Unsupported DATABASE_URL scheme: {scheme!r}. "
            f"Expected postgresql://, postgresql+<driver>://, or postgres://",
        )
    return make_url(database_url).set(drivername="postgresql+asyncpg")


async def main() -> None:
    args = parse_args()
    if args.batch_size <= 0:
        raise RuntimeError("--batch-size must be positive")

    import sqlalchemy as sa
    from dotenv import load_dotenv
    from sqlalchemy.ext.asyncio import create_async_engine

    load_dotenv()

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    url = build_async_url(database_url)
    engine = create_async_engine(url)

    try:
        async with engine.connect() as conn:
            total = (await conn.execute(sa.text("SELECT COUNT(*) FROM chunks"))).scalar() or 0
            if total == 0:
                print("No chunks to rebuild.")
                return

            print(f"Found {total} chunks.")
            if args.dry_run:
                print("Dry run only: no rows updated.")
                return

            last_id = 0
            updated = 0
            print(f"Rebuilding chunks.tsv in batches of {args.batch_size}...")

            while True:
                rows = (
                    await conn.execute(
                        sa.text(
                            "SELECT id, content FROM chunks "
                            "WHERE id > :last_id ORDER BY id LIMIT :lim"
                        ),
                        {"last_id": last_id, "lim": args.batch_size},
                    )
                ).fetchall()

                if not rows:
                    break

                params = [{"id": row.id, "content": row.content or ""} for row in rows]
                await conn.execute(
                    sa.text(
                        "UPDATE chunks "
                        "SET tsv = to_tsvector('simple', :content) "
                        "WHERE id = :id"
                    ),
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

    print(f"Done. {updated} chunks rebuilt without Kiwi.")


if __name__ == "__main__":
    asyncio.run(main())
