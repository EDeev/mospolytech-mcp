"""create tracked_groups

Revision ID: 5b1c7e2a9f40
Revises: d3ae49746cfb
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5b1c7e2a9f40'
down_revision: Union[str, Sequence[str], None] = 'd3ae49746cfb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('tracked_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_login', sa.String(length=100), nullable=False),
    sa.Column('group_name', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_login', 'group_name')
    )
    op.create_index(op.f('ix_tracked_groups_user_login'), 'tracked_groups', ['user_login'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tracked_groups_user_login'), table_name='tracked_groups')
    op.drop_table('tracked_groups')
