"""Phase 3 schema: content_source, summary_embedding, tsv, recommendations

Revision ID: phase3_0005
Revises: eeda241774f5
Create Date: 2026-02-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "phase3_0005"
down_revision: Union[str, None] = "eeda241774f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # links: content_source, summary_embedding
    op.add_column("links", sa.Column("content_source", sa.String(), nullable=True))
    op.execute("ALTER TABLE links ADD COLUMN summary_embedding vector(1536)")

    # chunks: tsvector column + GIN index
    op.execute("ALTER TABLE chunks ADD COLUMN tsv tsvector")
    op.create_index("idx_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")

    # recommendations table
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "link_id",
            sa.Integer(),
            sa.ForeignKey("links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "recommended_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_recommendations_user_date",
        "recommendations",
        ["user_id", "recommended_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_recommendations_user_date", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index("idx_chunks_tsv", table_name="chunks")
    op.drop_column("chunks", "tsv")
    op.drop_column("links", "summary_embedding")
    op.drop_column("links", "content_source")
