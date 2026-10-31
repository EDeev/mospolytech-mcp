"""student_profiles: полезные поля профиля ЛК отдельными столбцами

Revision ID: e7b2f4c81a90
Revises: adcdc720afa3
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e7b2f4c81a90'
down_revision: Union[str, Sequence[str], None] = 'adcdc720afa3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('student_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('surname', sa.String(length=100), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('patronymic', sa.String(length=100), nullable=True),
    sa.Column('group_name', sa.String(length=50), nullable=True),
    sa.Column('course', sa.SmallInteger(), nullable=True),
    sa.Column('faculty', sa.Text(), nullable=True),
    sa.Column('specialty', sa.Text(), nullable=True),
    sa.Column('specialty_code', sa.String(length=50), nullable=True),
    sa.Column('specialization', sa.Text(), nullable=True),
    sa.Column('education_form', sa.String(length=50), nullable=True),
    sa.Column('degree_level', sa.String(length=50), nullable=True),
    sa.Column('degree_length', sa.String(length=50), nullable=True),
    sa.Column('enter_year', sa.String(length=20), nullable=True),
    sa.Column('status', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    # заполнить из уже полученных профилей (personal_cache) — чтобы быстрый путь работал сразу после обновления
    op.execute("""
        INSERT INTO student_profiles (user_id, surname, name, patronymic, group_name, course, faculty, specialty,
            specialty_code, specialization, education_form, degree_level, degree_length, enter_year, status, email,
            updated_at)
        SELECT user_id, data->>'surname', data->>'name', data->>'patronymic', data->>'group',
            CASE WHEN data->>'course' ~ '^\\d+$' THEN (data->>'course')::smallint END,
            data->>'faculty', data->>'specialty', data->>'code', data->>'specialization', data->>'education_form',
            data->>'degree_level', data->>'degree_length',
            data->>'enter_year',
            data->>'status', data->>'email', fetched_at
        FROM personal_cache WHERE kind = 'profile' AND scope = ''
    """)


def downgrade() -> None:
    op.drop_table('student_profiles')
