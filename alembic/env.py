# Alembic env: настройка офлайн/онлайн-миграций и подключение к БД из .env.
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from mospolytech_mcp._dotenv import load_dotenv
from mospolytech_mcp.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
# адрес, переданный программно (тесты), важнее DATABASE_URL из окружения
if database_url := config.attributes.get("database_url") or os.environ.get("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Тайм-ауты в начале каждой транзакции миграций (и в SQL офлайн-режима --sql): миграция не ждёт блокировку
# дольше 5 с (иначе очередь за ней блокирует все запросы к таблице) и не выполняет один оператор дольше 5 мин.
# SET, а не SET LOCAL: значения действуют до конца соединения, в том числе в блоках autocommit_block().
TIMEOUTS = ("SET lock_timeout = '5s'", "SET statement_timeout = '5min'")


def run_with_timeouts() -> None:
    with context.begin_transaction():
        for statement in TIMEOUTS:
            context.execute(statement)
        context.run_migrations()


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    run_with_timeouts()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    run_with_timeouts()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    # psycopg в async-режиме не работает с ProactorEventLoop (по умолчанию на Windows)
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run_async_migrations(), loop_factory=loop_factory)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
