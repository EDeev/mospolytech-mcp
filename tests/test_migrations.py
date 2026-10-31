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
