"""Phase B: Rebuild chunk tsvectors with kiwipiepy morpheme tokenization.

Revision ID: phase_b_0006
Revises: phase3_0005
Create Date: 2026-03-15

WHY THIS MIGRATION EXISTS:
  Phase A stored tsvectors using to_tsvector('simple', raw_content).
  Korean compound words like '채용공고' became single unsplit tokens,
  so FTS queries for '채용' or '공고' produced sparse_score ≈ 0.

  Phase B uses kiwipiepy to pre-split compound words into morphemes before
  passing to PostgreSQL.  This migration backfills all existing chunks so
  their tsv column reflects morpheme-split tokens.

  EFFECT:
    Before: to_tsvector('simple', '채용공고 안내') → {'채용공고', '안내'}
    After:  to_tsvector('simple', '채용 공고 안내') → {'채용', '공고', '안내'}
    Queries for '채용' or '공고' now hit the GIN index → sparse_score > 0.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "phase_b_0006"
down_revision: Union[str, None] = "phase3_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BATCH_SIZE = 500


def _make_kiwi():
    """Initialize Kiwi once per migration run.

    Raises ImportError explicitly if kiwipiepy is not installed so the
    migration fails loudly rather than silently backfilling raw text.
    """
    try:
        from kiwipiepy import Kiwi  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "kiwipiepy is required for this migration. "
            "Run: pip install kiwipiepy"
        )
    return Kiwi()


def _tokenize(kiwi, text: str) -> str:
    tokens = kiwi.tokenize(text)
    return " ".join(
        t.form for t in tokens
        if t.tag.startswith(("NN", "VV", "SL", "XR"))
    )


def upgrade() -> None:
    """Rebuild all existing chunk tsvectors with morpheme tokenization.

    Uses cursor-based pagination (WHERE id > last_id) and batch executemany
    to avoid LIMIT/OFFSET scan degradation and per-row roundtrips.
    Kiwi is initialized once for the entire migration run.
    """
    kiwi = _make_kiwi()
    conn = op.get_bind()

    last_id = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id, content FROM chunks "
                "WHERE id > :last_id ORDER BY id LIMIT :lim"
            ),
            {"last_id": last_id, "lim": _BATCH_SIZE},
        ).fetchall()

        if not rows:
            break

        params = [
            {"mc": _tokenize(kiwi, row.content or ""), "id": row.id}
            for row in rows
        ]
        conn.execute(
            sa.text("UPDATE chunks SET tsv = to_tsvector('simple', :mc) WHERE id = :id"),
            params,
        )

        last_id = rows[-1].id

    conn.execute(sa.text("ANALYZE chunks"))


def downgrade() -> None:
    """Revert tsvectors to raw content (Phase A behaviour)."""
    conn = op.get_bind()

    last_id = 0
    while True:
        rows = conn.execute(
            sa.text(
                "SELECT id, content FROM chunks "
                "WHERE id > :last_id ORDER BY id LIMIT :lim"
            ),
            {"last_id": last_id, "lim": _BATCH_SIZE},
        ).fetchall()

        if not rows:
            break

        params = [
            {"c": row.content or "", "id": row.id}
            for row in rows
        ]
        conn.execute(
            sa.text("UPDATE chunks SET tsv = to_tsvector('simple', :c) WHERE id = :id"),
            params,
        )

        last_id = rows[-1].id

    conn.execute(sa.text("ANALYZE chunks"))
