"""add memo column and make url nullable in links

Revision ID: b833c9c53c33
Revises: 0001
Create Date: 2026-02-22 04:00:20.592300

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b833c9c53c33'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('links', sa.Column('memo', sa.Text(), nullable=True))
    op.alter_column('links', 'url', existing_type=sa.VARCHAR(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM links WHERE url IS NULL"))
    op.alter_column('links', 'url', existing_type=sa.VARCHAR(), nullable=False)
    op.drop_column('links', 'memo')
