"""schedule cache, teacher index, service state

Revision ID: 2168974c74e6
Revises: b1747cf96ce4
Create Date: 2026-10-07 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '2168974c74e6'
down_revision: Union[str, Sequence[str], None] = 'b1747cf96ce4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('schedule_cache',
    sa.Column('group_name', sa.String(length=50), nullable=False),
    sa.Column('is_session', sa.Boolean(), nullable=False),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('group_name', 'is_session')
    )
    op.create_table('teacher_lessons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher', sa.String(length=200), nullable=False),
    sa.Column('group_name', sa.String(length=50), nullable=False),
    sa.Column('is_session', sa.Boolean(), nullable=False),
    sa.Column('weekday', sa.SmallInteger(), nullable=True),
    sa.Column('lesson_date', sa.Date(), nullable=True),
    sa.Column('pair', sa.SmallInteger(), nullable=False),
    sa.Column('subject', sa.String(length=300), nullable=False),
    sa.Column('lesson_type', sa.String(length=100), nullable=False),
    sa.Column('rooms', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('location', sa.String(length=200), nullable=False),
    sa.Column('link', sa.Text(), nullable=True),
    sa.Column('date_from', sa.Date(), nullable=False),
    sa.Column('date_to', sa.Date(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_teacher_lessons_teacher'), 'teacher_lessons', ['teacher'], unique=False)
    op.create_index(op.f('ix_teacher_lessons_group_name'), 'teacher_lessons', ['group_name'], unique=False)
    op.create_table('service_state',
    sa.Column('key', sa.String(length=50), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )


def downgrade() -> None:
    op.drop_table('service_state')
    op.drop_index(op.f('ix_teacher_lessons_group_name'), table_name='teacher_lessons')
    op.drop_index(op.f('ix_teacher_lessons_teacher'), table_name='teacher_lessons')
    op.drop_table('teacher_lessons')
    op.drop_table('schedule_cache')
