"""Phase B: historical marker for morpheme-tokenization tsvector rebuild.

Revision ID: phase_b_0006
Revises: phase3_0005
Create Date: 2026-03-15

NOTE: This migration contains no schema changes (DDL).
The `tsv` column and GIN index were added in `phase3_0005`.

Historically, the Kiwi rollout rebuilt existing `chunks.tsv` values out of band.
This revision remains only as a migration-history marker for that rollout.

It must not be treated as a deploy-time or rollback-time mechanism:
- Kiwi rollback is handled separately from Alembic history.
- Current recovery guidance lives in
  `docs/troubleshooting/2026-03-18-kiwi-rollback-tsv-regeneration.md`.
"""

from __future__ import annotations

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "phase_b_0006"
down_revision: Union[str, None] = "phase3_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass  # Historical marker only; data recovery is handled outside Alembic


def downgrade() -> None:
    pass  # No schema changes to revert
