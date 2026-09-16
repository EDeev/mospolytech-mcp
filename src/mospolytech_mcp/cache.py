# Кэш списка групп с TTL поверх БД, с fallback на просроченный кэш при сбое источника.

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import GroupsCache
from .open_api import OpenDataClient

DEFAULT_GROUPS_TTL = timedelta(minutes=15)


class GroupsCacheStore:
    def __init__(
        self,
        open_client: OpenDataClient,
        sessionmaker: async_sessionmaker,
        *,
        ttl: timedelta = DEFAULT_GROUPS_TTL,
    ) -> None:
        self._open = open_client
        self._sessionmaker = sessionmaker
        self._ttl = ttl

    async def get_groups(self) -> list[str]:
        async with self._sessionmaker() as session:
            row = await session.get(GroupsCache, 1)
            now = datetime.now(UTC)

            if row is not None and now - row.fetched_at < self._ttl:
                return row.groups

            try:
                groups = await self._open.get_groups()
            except Exception:
                if row is not None:
                    return row.groups
                raise

            if row is None:
                session.add(GroupsCache(id=1, groups=groups, fetched_at=now))
            else:
                row.groups = groups
                row.fetched_at = now
            await session.commit()
            return groups
