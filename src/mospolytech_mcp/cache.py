# Кэш справочных данных в БД с TTL и откатом на просроченный кэш при сбое источника (ФХД-003, ТН-001).

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import GroupsCache, ScheduleCache
from .open_api import OpenDataClient
from .schedule_format import lessons_from_open_schedule

DEFAULT_GROUPS_TTL = timedelta(minutes=15)
DEFAULT_SCHEDULE_TTL = timedelta(hours=6)


class SourceUnavailableError(RuntimeError):
    """Источник не ответил, а в кэше ничего нет."""


class ScheduleNotFoundError(LookupError):
    pass


@dataclass
class Cached:
    data: Any
    fetched_at: datetime
    from_cache: bool
    stale: bool = False
    error: str | None = None

    def meta(self) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "source": "кэш" if self.from_cache else "источник",
            "fetched_at": self.fetched_at.astimezone().isoformat(timespec="seconds"),
        }
        if self.stale:
            meta["stale"] = True
            meta["note"] = f"источник недоступен ({self.error}), показаны данные из кэша"
        return meta


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


class ScheduleCacheStore:
    """Расписание группы (семестр/сессия) в виде плоского списка занятий, с TTL."""

    def __init__(
        self,
        open_client: OpenDataClient,
        sessionmaker: async_sessionmaker,
        *,
        ttl: timedelta = DEFAULT_SCHEDULE_TTL,
    ) -> None:
        self._open = open_client
        self._sessionmaker = sessionmaker
        self._ttl = ttl

    async def get(self, group: str, *, is_session: bool) -> Cached:
        group = group.strip()
        async with self._sessionmaker() as session:
            row = await session.get(ScheduleCache, (group, is_session))
        now = datetime.now(UTC)
        if row is not None and now - row.fetched_at < self._ttl:
            return Cached(row.data, row.fetched_at, from_cache=True)

        try:
            raw = await self._open.get_schedule(group, is_session=is_session)
        except ValueError as exc:
            # источник ответил: расписания нет (ещё не готово / пустое)
            kind = "сессии" if is_session else "семестра"
            raise ScheduleNotFoundError(f"расписания {kind} для группы {group} нет") from exc
        except Exception as exc:
            if row is not None:
                return Cached(row.data, row.fetched_at, from_cache=True, stale=True, error=_short(exc))
            raise SourceUnavailableError(
                f"открытое API расписания недоступно ({_short(exc)}), а в кэше группы {group} нет"
            ) from exc

        data = schedule_payload(raw)
        await self.put(group, is_session=is_session, data=data, fetched_at=now)
        return Cached(data, now, from_cache=False)

    async def put(
        self, group: str, *, is_session: bool, data: dict[str, Any], fetched_at: datetime
    ) -> None:
        stmt = insert(ScheduleCache).values(
            group_name=group, is_session=is_session, data=data, fetched_at=fetched_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["group_name", "is_session"],
            set_={"data": stmt.excluded.data, "fetched_at": stmt.excluded.fetched_at},
        )
        async with self._sessionmaker() as session:
            await session.execute(stmt)
            await session.commit()


def schedule_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Ответ mospolytech_api → то, что храним в schedule_cache.data."""
    date_from, date_to = (raw.get("dates") or ["", ""])[:2]
    return {
        "group": raw.get("group"),
        "evening": raw.get("type") == "evening",
        "period": [date_from, date_to],
        "lessons": lessons_from_open_schedule(raw),
    }


def _short(exc: BaseException) -> str:
    text = str(exc) or type(exc).__name__
    return text if len(text) <= 200 else text[:200] + "…"
