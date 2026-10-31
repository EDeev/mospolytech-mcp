"""lk_access_log: индекс по времени обращения

Revision ID: c3d9f2a71e05
Revises: b8a323584ccb
Create Date: 2026-10-31 22:30:00.000000

Журнал обращений к личному кабинету растёт с каждым запросом; выборки и очистка журнала за период идут по
created_at без учёта пользователя, а существующий индекс (user_id, created_at) для них не подходит.
Индекс строится CONCURRENTLY вне транзакции — запись в журнал во время построения не блокируется;
IF NOT EXISTS делает шаг повторяемым, если миграция прервётся.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d9f2a71e05"
down_revision: Union[str, Sequence[str], None] = "b8a323584ccb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_lk_access_log_created_at",
            "lk_access_log",
            ["created_at"],
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_lk_access_log_created_at",
            table_name="lk_access_log",
            postgresql_concurrently=True,
            if_exists=True,
        )
