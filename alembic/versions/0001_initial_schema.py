"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-02-21

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # pgvector 확장 활성화
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # users 테이블
    op.create_table(
        "users",
        sa.Column("telegram_id", sa.BigInteger(), primary_key=True),
        sa.Column("notion_access_token", sa.String(), nullable=True),
        sa.Column("notion_page_id", sa.String(), nullable=True),
    )

    # links 테이블
    op.create_table(
        "links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.telegram_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("keywords", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "url", name="uq_user_url"),
    )

    # chunks 테이블
    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "link_id",
            sa.Integer(),
            sa.ForeignKey("links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
    )

    # IVFFlat 인덱스 (코사인 유사도)
    op.execute(
        "CREATE INDEX chunks_embedding_idx ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.drop_table("chunks")
    op.drop_table("links")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
