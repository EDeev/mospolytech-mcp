# Подключение к БД: движок и фабрика сессий из DATABASE_URL.

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL не задан — скопируйте .env.example в .env и заполните его"
        )
    return url


def make_engine(database_url: str | None = None) -> AsyncEngine:
    return create_async_engine(database_url or _database_url())


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
