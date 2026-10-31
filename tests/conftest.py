# Общие фикстуры. Интеграционные тесты идут на PostgreSQL из TEST_DATABASE_URL — каждый прогон во временной
# схеме (создаётся, накатываются миграции Alembic, в конце удаляется). Без TEST_DATABASE_URL они пропускаются.

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import text

from mospolytech_mcp._dotenv import load_dotenv
from mospolytech_mcp.db import Base, make_engine, make_sessionmaker
from mospolytech_mcp.server import Services, build_services
from mospolytech_mcp.settings import Settings

from .fakes import FakeLK, FakeOpenData

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


if sys.platform == "win32":
    # psycopg в async-режиме не работает с ProactorEventLoop (по умолчанию на Windows). Хук — только здесь:
    # новые pytest-asyncio не принимают None из него (UsageError на Linux).
    def pytest_asyncio_loop_factories(config, item):
        return {"selector": asyncio.SelectorEventLoop}


def alembic_config(url: str) -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


def _sync_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _with_schema(url: str, schema: str) -> str:
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}options={quote(f'-csearch_path={schema}')}"


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL не задан — интеграционные тесты с PostgreSQL пропущены")
    return url


@pytest.fixture(scope="session")
def make_schema(database_url):
    """Создаёт временные схемы и удаляет их в конце сессии."""
    created: list[str] = []

    def create() -> str:
        schema = "test_" + uuid.uuid4().hex[:12]
        with psycopg.connect(_sync_url(database_url), autocommit=True) as conn:
            conn.execute(f'CREATE SCHEMA "{schema}"')
        created.append(schema)
        return _with_schema(database_url, schema)

    yield create
    with psycopg.connect(_sync_url(database_url), autocommit=True) as conn:
        for schema in created:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


@pytest.fixture(scope="session")
def migrated_url(make_schema) -> str:
    url = make_schema()
    command.upgrade(alembic_config(url), "head")
    return url


@pytest.fixture
async def sessionmaker(migrated_url):
    engine = make_engine(migrated_url, pool_size=5)
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield make_sessionmaker(engine)
    await engine.dispose()


@pytest.fixture
def fake_open() -> FakeOpenData:
    return FakeOpenData()


@pytest.fixture
def fake_lk() -> FakeLK:
    return FakeLK()


@pytest.fixture
def settings() -> Settings:
    return Settings(secret_key=Fernet.generate_key().decode(), teacher_index=False)


@pytest.fixture
def services(settings, sessionmaker, fake_open, fake_lk) -> Services:
    return build_services(settings, sessionmaker, mode="http", open_client=fake_open, lk_factory=fake_lk.factory)
