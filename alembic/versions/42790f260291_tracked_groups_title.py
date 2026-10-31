"""tracked_groups: заголовок отслеживаемой группы

Revision ID: 42790f260291
Revises: e7b2f4c81a90
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '42790f260291'
down_revision: Union[str, Sequence[str], None] = 'e7b2f4c81a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tracked_groups', sa.Column('title', sa.Text(), nullable=False))
    op.drop_column('tracked_groups', 'created_at')
    op.create_index('ix_tracked_groups_title', 'tracked_groups', ['title'], unique=False)
    op.alter_column('tracked_groups', 'group_name', type_=sa.String(length=100), existing_nullable=False)


def downgrade() -> None:
    op.alter_column('tracked_groups', 'group_name', type_=sa.String(length=50), existing_nullable=False)
    op.drop_index('ix_tracked_groups_title', table_name='tracked_groups')
    op.add_column('tracked_groups', sa.Column('created_at', sa.DateTime(timezone=True),
                                              server_default=sa.text('now()'), nullable=False))
    op.drop_column('tracked_groups', 'title')
