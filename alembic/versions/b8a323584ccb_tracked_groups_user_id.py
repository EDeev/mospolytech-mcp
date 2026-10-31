"""tracked_groups: привязка к пользователю по user_id с внешним ключом на users

Revision ID: b8a323584ccb
Revises: e7b2f4c81a90
Create Date: 2026-10-31 12:00:00.000000

Расширение (expand) по схеме expand/contract: отслеживаемые группы были привязаны к пользователю строкой
user_login без связи с users. Добавляется user_id с внешним ключом на users(id) ON DELETE CASCADE, user_login
остаётся (код по-прежнему его заполняет) — его удаление вместе со старым уникальным ограничением
(user_login, group_name) — отдельный будущий шаг сжатия (contract).

Порядок рассчитан на живую БД без долгих блокировок:
1. транзакция 1: столбец user_id без NOT NULL, заполнение по логину, удаление строк без пользователя; внешний
   ключ и CHECK (user_id IS NOT NULL) — с NOT VALID: существующие строки не проверяются, блокировка короткая;
2. вне транзакции: уникальный индекс (user_id, group_name) — CREATE INDEX CONCURRENTLY (не блокирует запись);
3. транзакция 2 (вместе с записью новой ревизии в alembic_version): VALIDATE CONSTRAINT — проверка строк под
   блокировкой SHARE UPDATE EXCLUSIVE, чтение и запись не блокируются; SET NOT NULL — PostgreSQL опирается на
   проверенный CHECK и не сканирует таблицу (CHECK остаётся: удалять ограничения squawk запрещает); ограничение
   UNIQUE USING INDEX поверх готового индекса.
VALIDATE — в отдельной от NOT VALID транзакции (иначе блокировка от ADD CONSTRAINT держалась бы всю проверку) и
в той же, что и запись ревизии: squawk (prefer-robust-stmts) считает повторяемыми только такие транзакции.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8a323584ccb'
down_revision: Union[str, Sequence[str], None] = 'e7b2f4c81a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK = 'fk_tracked_groups_user_id_users'
CHECK = 'ck_tracked_groups_user_id_not_null'
UNIQUE = 'uq_tracked_groups_user_id_group_name'


def upgrade() -> None:
    op.add_column('tracked_groups', sa.Column('user_id', sa.Integer(), nullable=True))
    op.execute("UPDATE tracked_groups SET user_id = users.id FROM users WHERE users.login = tracked_groups.user_login")
    # строки с логином, которого нет в users, ни одному пользователю не видны — привязать их не к кому
    op.execute("DELETE FROM tracked_groups WHERE user_id IS NULL")
    op.execute(
        f"ALTER TABLE tracked_groups ADD CONSTRAINT {FK} "
        "FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE NOT VALID"
    )
    op.execute(f"ALTER TABLE tracked_groups ADD CONSTRAINT {CHECK} CHECK (user_id IS NOT NULL) NOT VALID")

    # фиксирует транзакцию 1; CREATE INDEX CONCURRENTLY внутри транзакции не выполняется; затем — транзакция 2
    with op.get_context().autocommit_block():
        op.execute(f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {UNIQUE} ON tracked_groups (user_id, group_name)")

    op.execute(f"ALTER TABLE tracked_groups VALIDATE CONSTRAINT {FK}")
    op.execute(f"ALTER TABLE tracked_groups VALIDATE CONSTRAINT {CHECK}")
    op.alter_column('tracked_groups', 'user_id', existing_type=sa.Integer(), nullable=False)
    op.execute(f"ALTER TABLE tracked_groups ADD CONSTRAINT {UNIQUE} UNIQUE USING INDEX {UNIQUE}")


def downgrade() -> None:
    op.drop_constraint(UNIQUE, 'tracked_groups', type_='unique')
    op.drop_constraint(CHECK, 'tracked_groups', type_='check')
    op.drop_constraint(FK, 'tracked_groups', type_='foreignkey')
    op.drop_column('tracked_groups', 'user_id')
