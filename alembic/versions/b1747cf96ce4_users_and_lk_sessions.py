"""users, lk sessions, api keys, lk access log

Revision ID: b1747cf96ce4
Revises: 5b1c7e2a9f40
Create Date: 2026-10-07 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1747cf96ce4'
down_revision: Union[str, Sequence[str], None] = '5b1c7e2a9f40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('guid', sa.String(length=64), nullable=False),
    sa.Column('login', sa.String(length=100), nullable=False),
    sa.Column('full_name', sa.String(length=300), nullable=False),
    sa.Column('group_name', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('guid'),
    sa.UniqueConstraint('login')
    )
    op.create_table('user_sessions',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_enc', sa.Text(), nullable=False),
    sa.Column('jwt_enc', sa.Text(), nullable=False),
    sa.Column('jwt_refresh_enc', sa.Text(), nullable=False),
    sa.Column('refreshed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('api_keys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)
    op.create_table('lk_access_log',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('login', sa.String(length=100), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lk_access_log_user_created', 'lk_access_log', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_lk_access_log_user_created', table_name='lk_access_log')
    op.drop_table('lk_access_log')
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_table('user_sessions')
    op.drop_table('users')
