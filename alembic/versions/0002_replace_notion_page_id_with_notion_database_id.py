"""replace notion_page_id with notion_database_id in users

Revision ID: 18a3b385bd6f
Revises: b833c9c53c33
Create Date: 2026-02-22 04:05:08.819686

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '18a3b385bd6f'
down_revision: Union[str, None] = 'b833c9c53c33'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # notion_page_id(페이지 ID)와 notion_database_id(데이터베이스 ID)는 다른 개념이므로
    # 기존 데이터 마이그레이션 불가. 이 마이그레이션 적용 후 기존 유저는 /start로 재연동 필요.
    op.add_column('users', sa.Column('notion_database_id', sa.String(), nullable=True))
    op.drop_column('users', 'notion_page_id')


def downgrade() -> None:
    op.add_column('users', sa.Column('notion_page_id', sa.VARCHAR(), autoincrement=False, nullable=True))
    op.drop_column('users', 'notion_database_id')
