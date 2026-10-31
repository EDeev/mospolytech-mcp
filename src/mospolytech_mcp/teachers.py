# Расписание преподавателя из открытых данных (ФОД-003): индекс занятий, собранный из расписаний всех групп.
#
# У rasp.dmami.ru нет запроса по преподавателю, а getScheduleTeacher в ЛК требует входа (противоречит ТЭ-001).
# Поэтому раз в сутки сервер проходит расписания всех групп (семестр — по группе, сессия — одним файлом),
# раскладывает занятия по преподавателям в teacher_lessons и попутно прогревает schedule_cache.

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from .cache import ScheduleCacheStore, schedule_payload
from .db import ServiceState, TeacherLesson
from .open_api import OpenDataClient

log = logging.getLogger(__name__)

STATE_KEY = "teacher_index"
# pg_try_advisory_lock: индекс собирает только один процесс, даже если серверов запущено несколько
ADVISORY_LOCK_ID = 72150001
INSERT_CHUNK = 1000


class IndexNotReadyError(RuntimeError):
    pass


def _normalize(value: str) -> str:
    return value.lower().replace("ё", "е")


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-zа-я]+", _normalize(value))


def match_teachers(query: str, names: list[str]) -> list[str]:
    """Преподаватели по ФИО или его части.

    Сначала слова запроса сверяются по порядку с фамилией, именем, отчеством («Васильев», «Васильев Д. Б.»,
    «Васил») — и если фамилия совпала целиком, остаются только такие. Если по порядку никто не подошёл —
    каждое слово ищется в любом месте ФИО («Денис Борисович»). Полное совпадение ФИО побеждает всё.
    """
    wanted = _tokens(query)
    if not wanted:
        return []
    split = {name: _tokens(name) for name in names}
    exact = [n for n, words in split.items() if words == wanted]
    if exact:
        return exact
    ordered = [
        n for n, words in split.items()
        if len(words) >= len(wanted) and all(words[i].startswith(t) for i, t in enumerate(wanted))
    ]
    if ordered:
        same_surname = [n for n in ordered if split[n][0] == wanted[0]]
        return sorted(same_surname or ordered)
    return sorted(n for n, words in split.items() if all(any(w.startswith(t) for w in words) for t in wanted))


def teacher_rows(group: str, payload: dict[str, Any], *, is_session: bool) -> list[dict[str, Any]]:
    rows = []
    for lesson in payload["lessons"]:
        for teacher in lesson["teachers"]:
            rows.append(
                {
                    "teacher": teacher[:200],
                    "group_name": group,
                    "is_session": is_session,
                    "weekday": lesson["weekday"],
                    "lesson_date": date.fromisoformat(lesson["date"]) if lesson["date"] else None,
                    "pair": lesson["pair"],
                    "subject": lesson["subject"][:300],
                    "lesson_type": lesson["type"][:100],
                    "rooms": lesson["rooms"],
                    "location": lesson["location"][:200],
                    "link": lesson["link"],
                    "date_from": date.fromisoformat(lesson["date_from"]),
                    "date_to": date.fromisoformat(lesson["date_to"]),
                }
            )
    return rows


class TeacherIndex:
    def __init__(
        self,
        open_client: OpenDataClient,
        sessionmaker: async_sessionmaker,
        schedules: ScheduleCacheStore,
        *,
        ttl: timedelta = timedelta(hours=24),
        concurrency: int = 4,
        delay: float = 0.1,
    ) -> None:
        self._open = open_client
        self._sessionmaker = sessionmaker
        self._schedules = schedules
        self._ttl = ttl
        self._concurrency = concurrency
        self._delay = delay
        self._names: list[str] | None = None
        self._names_built_at: str | None = None

    async def status(self) -> dict[str, Any] | None:
        async with self._sessionmaker() as session:
            row = await session.get(ServiceState, STATE_KEY)
            return dict(row.value) if row is not None else None

    async def needs_rebuild(self) -> bool:
        state = await self.status()
        if state is None:
            return True
        built_at = datetime.fromisoformat(state["built_at"])
        return datetime.now(UTC) - built_at >= self._ttl

    async def rebuild(self) -> dict[str, Any] | None:
        """Пересобрать индекс. None — если его прямо сейчас собирает другой процесс."""
        async with self._sessionmaker() as lock_session:
            conn = await lock_session.connection(execution_options={"isolation_level": "AUTOCOMMIT"})
            locked = await conn.scalar(text("SELECT pg_try_advisory_lock(:id)"), {"id": ADVISORY_LOCK_ID})
            if not locked:
                return None
            try:
                return await self._rebuild()
            finally:
                await conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": ADVISORY_LOCK_ID})

    async def _rebuild(self) -> dict[str, Any]:
        started = datetime.now(UTC)
        groups = await self._open.get_groups()
        semester_rows: list[dict[str, Any]] = []
        stats = {"groups": len(groups), "semester_ok": 0, "semester_empty": 0, "semester_failed": 0}
        semaphore = asyncio.Semaphore(self._concurrency)

        async def one(group: str) -> None:
            async with semaphore:
                try:
                    raw = await self._open.get_schedule(group, is_session=False)
                    payload = schedule_payload(raw)
                except ValueError:
                    stats["semester_empty"] += 1
                    return
                except Exception as exc:  # одна сломанная группа не должна ронять весь индекс
                    stats["semester_failed"] += 1
                    log.warning("индекс преподавателей: группа %s: %s", group, exc)
                    return
                finally:
                    await asyncio.sleep(self._delay)
                await self._schedules.put(group, is_session=False, data=payload, fetched_at=datetime.now(UTC))
                semester_rows.extend(teacher_rows(group, payload, is_session=False))
                stats["semester_ok"] += 1

        await asyncio.gather(*(one(g) for g in groups))
        if stats["semester_ok"] == 0:
            raise RuntimeError(f"индекс не пересобран: ни одного расписания не получено ({stats})")
        await self._replace(is_session=False, rows=semester_rows)

        session_rows: list[dict[str, Any]] = []
        try:
            sessions = await self._open.get_session()
        except Exception as exc:
            stats["session_error"] = str(exc)[:200]
            log.warning("индекс преподавателей: файл сессии недоступен: %s", exc)
        else:
            now = datetime.now(UTC)
            for group, item in sessions.items():
                raw = {"group": group, "is_session": True, **item}
                payload = schedule_payload(raw)
                await self._schedules.put(group, is_session=True, data=payload, fetched_at=now)
                session_rows.extend(teacher_rows(group, payload, is_session=True))
            await self._replace(is_session=True, rows=session_rows)
            stats["session_groups"] = len(sessions)

        state = {
            **stats,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "seconds": round((datetime.now(UTC) - started).total_seconds()),
            "lessons": len(semester_rows) + len(session_rows),
            "teachers": len({r["teacher"] for r in semester_rows} | {r["teacher"] for r in session_rows}),
        }
        async with self._sessionmaker() as session:
            await session.merge(ServiceState(key=STATE_KEY, value=state, updated_at=datetime.now(UTC)))
            await session.commit()
        self._names = None
        log.info("индекс преподавателей пересобран: %s", state)
        return state

    async def _replace(self, *, is_session: bool, rows: list[dict[str, Any]]) -> None:
        async with self._sessionmaker() as session:
            await session.execute(delete(TeacherLesson).where(TeacherLesson.is_session == is_session))
            # один INSERT … VALUES (…), (…) на пачку: executemany шёл бы к БД по строке за раз
            for i in range(0, len(rows), INSERT_CHUNK):
                await session.execute(insert(TeacherLesson).values(rows[i : i + INSERT_CHUNK]))
            await session.commit()

    async def names(self) -> list[str]:
        state = await self.status()
        if state is None:
            raise IndexNotReadyError(
                "индекс преподавателей ещё не собран — сервер собирает его в фоне из расписаний всех групп, "
                "обычно это пара минут"
            )
        if self._names is None or self._names_built_at != state["built_at"]:
            async with self._sessionmaker() as session:
                self._names = list(await session.scalars(select(TeacherLesson.teacher).distinct()))
            self._names_built_at = state["built_at"]
        return self._names

    async def find(self, query: str) -> list[str]:
        return match_teachers(query, await self.names())

    async def lessons(self, teacher: str, *, is_session: bool) -> list[dict[str, Any]]:
        stmt = select(TeacherLesson).where(
            TeacherLesson.teacher == teacher, TeacherLesson.is_session == is_session
        )
        async with self._sessionmaker() as session:
            rows = list(await session.scalars(stmt))
        return [
            {
                "group": r.group_name,
                "weekday": r.weekday,
                "date": r.lesson_date.isoformat() if r.lesson_date else None,
                "pair": r.pair,
                "subject": r.subject,
                "type": r.lesson_type,
                "rooms": r.rooms,
                "location": r.location,
                "link": r.link,
                "date_from": r.date_from.isoformat(),
                "date_to": r.date_to.isoformat(),
            }
            for r in rows
        ]

    async def run_forever(self, check_every: timedelta = timedelta(hours=1)) -> None:
        while True:
            try:
                if await self.needs_rebuild():
                    await self.rebuild()
            except Exception:
                log.exception("индекс преподавателей: ошибка пересборки")
            await asyncio.sleep(check_every.total_seconds())


async def _rebuild_once() -> None:
    from pathlib import Path

    from ._dotenv import load_dotenv
    from .db import make_engine, make_sessionmaker
    from .settings import Settings

    load_dotenv(Path.cwd() / ".env")
    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    sessionmaker = make_sessionmaker(engine)
    open_client = OpenDataClient()
    index = TeacherIndex(open_client, sessionmaker, ScheduleCacheStore(open_client, sessionmaker))
    try:
        state = await index.rebuild()
        print(state if state is not None else "индекс сейчас собирает другой процесс")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    asyncio.run(_rebuild_once(), loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None)
