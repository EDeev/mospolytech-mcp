# Миграции Alembic: накатываются с нуля, полностью откатываются и совпадают с моделями SQLAlchemy.

from __future__ import annotations

import psycopg
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from mospolytech_mcp.db import Base

from .conftest import _sync_url, alembic_config

TABLES = {
    "alembic_version", "groups_cache", "tracked_groups", "users", "user_sessions", "api_keys", "lk_access_log",
    "schedule_cache", "teacher_lessons", "service_state", "personal_cache", "personal_history", "notifications",
    "student_profiles",
}


def _tables(url: str) -> set[str]:
    with psycopg.connect(_sync_url(url)) as conn:
        rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()").fetchall()
    return {r[0] for r in rows}


def test_upgrade_downgrade_roundtrip(make_schema):
    url = make_schema()
    cfg = alembic_config(url)
    command.upgrade(cfg, "head")
    assert _tables(url) == TABLES
    command.downgrade(cfg, "base")
    assert _tables(url) == {"alembic_version"}
    command.upgrade(cfg, "head")
    assert _tables(url) == TABLES


def test_models_match_migrations(migrated_url):
    engine = create_engine(migrated_url)
    with engine.connect() as conn:
        changes = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert changes == []


def test_tracked_groups_user_id_backfill(make_schema):
    # b8a323584ccb: tracked_groups получает user_id по логину; строки без пользователя удаляются
    url = make_schema()
    cfg = alembic_config(url)
    command.upgrade(cfg, "e7b2f4c81a90")
    with psycopg.connect(_sync_url(url)) as conn:
        user_id = conn.execute(
            "INSERT INTO users (guid, login, full_name, last_login_at) "
            "VALUES ('guid-1', 'deev.e.v', 'Деев Егор', now()) RETURNING id"
        ).fetchone()[0]
        conn.execute(
            "INSERT INTO tracked_groups (user_login, group_name) VALUES ('deev.e.v', '241-327'), ('nobody', '241-328')"
        )

    command.upgrade(cfg, "b8a323584ccb")
    with psycopg.connect(_sync_url(url)) as conn:
        rows = conn.execute("SELECT user_id, user_login, group_name FROM tracked_groups").fetchall()
        assert rows == [(user_id, "deev.e.v", "241-327")]
        # внешний ключ ON DELETE CASCADE: группы удаляются вместе с пользователем
        conn.execute("DELETE FROM users WHERE id = %s", (user_id,))
        assert conn.execute("SELECT count(*) FROM tracked_groups").fetchone()[0] == 0
