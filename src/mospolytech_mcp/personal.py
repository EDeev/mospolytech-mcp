# Персональные данные из ЛК: кэш с TTL и откатом (ФХД-001, ТН-001), история изменений (ФХД-002),
# уведомления без дублей.

from __future__ import annotations

import asyncio
import dataclasses
import logging
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from .auth import LKGateway, LKUnavailableError, SessionExpiredError
from .cache import Cached
from .db import Notification, PersonalCache, PersonalHistory, StudentProfile
from .lk_api import LKClient

log = logging.getLogger(__name__)

HISTORY_KINDS = ("performance", "payments", "requests")
MAX_DIFF_LINES = 100


class PersonalDataError(Exception):
    """Данных нет ни из ЛК, ни в кэше; текст — для пользователя."""


def to_plain(obj: Any) -> Any:
    """dataclass-модели lk_api → JSON-совместимые dict/list, без сырых ответов (поле raw)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name.rstrip("_"): to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj) if f.name != "raw"}
    if isinstance(obj, dict):
        return {str(k): to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(x) for x in obj]
    return obj


def data_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def diff(old: Any, new: Any, path: str = "") -> list[str]:
    """Человекочитаемые отличия двух срезов: «[id=12].grade: Хорошо → Отлично»."""
    if isinstance(old, dict) and isinstance(new, dict):
        lines = []
        for key in sorted(set(old) | set(new)):
            sub = f"{path}.{key}" if path else key
            if key not in old:
                lines.append(f"{sub}: добавлено {new[key]!r}")
            elif key not in new:
                lines.append(f"{sub}: удалено")
            else:
                lines.extend(diff(old[key], new[key], sub))
        return lines
    if _keyed(old) and _keyed(new):
        before = {str(x["id"]): x for x in old}
        after = {str(x["id"]): x for x in new}
        lines = []
        for key in sorted(set(before) | set(after)):
            sub = f"{path}[id={key}]"
            if key not in before:
                lines.append(f"{sub}: новая запись {_label(after[key])}")
            elif key not in after:
                lines.append(f"{sub}: запись исчезла {_label(before[key])}")
            else:
                lines.extend(diff(before[key], after[key], sub))
        return lines
    if old != new:
        return [f"{path}: {old!r} → {new!r}"]
    return []


# Профиль ЛК → столбцы student_profiles: только нужное (без телефона, дня рождения, финансов, приказов, пропуска).
_PROFILE_COLUMNS = {
    "surname": "surname",
    "name": "name",
    "patronymic": "patronymic",
    "group": "group_name",
    "faculty": "faculty",
    "specialty": "specialty",
    "code": "specialty_code",
    "specialization": "specialization",
    "education_form": "education_form",
    "degree_level": "degree_level",
    "degree_length": "degree_length",
    "enter_year": "enter_year",
    "status": "status",
    "email": "email",
}


def _profile_upsert(user_id: int, data: dict[str, Any], now: datetime):
    values: dict[str, Any] = {col: (str(data[src]).strip() or None) if data.get(src) is not None else None
                              for src, col in _PROFILE_COLUMNS.items()}
    course = str(data.get("course") or "").strip()
    values["course"] = int(course) if course.isdigit() else None
    stmt = insert(StudentProfile).values(user_id=user_id, updated_at=now, **values)
    return stmt.on_conflict_do_update(
        index_elements=["user_id"], set_={**{k: stmt.excluded[k] for k in values}, "updated_at": stmt.excluded.updated_at}
    )


def _keyed(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(x, dict) and "id" in x for x in value)


def _label(item: dict[str, Any]) -> str:
    for field in ("name", "subject", "title", "number"):
        if item.get(field):
            return f"«{item[field]}»"
    return ""


class PersonalData:
    def __init__(
        self,
        sessionmaker: async_sessionmaker,
        gateway: LKGateway,
        ttl: dict[str, timedelta],
    ) -> None:
        self._sessionmaker = sessionmaker
        self._gateway = gateway
        self._ttl = ttl
        self._background: dict[tuple[int, str, str], asyncio.Task] = {}

    async def get(
        self,
        user_id: int,
        kind: str,
        fetch: Callable[[LKClient], Awaitable[Any]],
        *,
        scope: str = "",
        refresh: bool = False,
        background: bool = False,
    ) -> Cached:
        """Свежий кэш → он; иначе ЛК; ЛК недоступен или сессия истекла → просроченный кэш с пометкой.

        background=True — просроченный кэш отдаётся сразу, а ЛК опрашивается в фоне (для профиля: ЛК отвечает на
        getUser до 25 с, а профиль меняется редко)."""
        async with self._sessionmaker() as session:
            row = await session.get(PersonalCache, (user_id, kind, scope))
        now = datetime.now(UTC)
        ttl = self._ttl.get(kind, timedelta(minutes=5))
        if row is not None and not refresh and now - row.fetched_at < ttl:
            return Cached(row.data, row.fetched_at, from_cache=True)
        if row is not None and not refresh and background:
            self._refresh_in_background(user_id, kind, scope, fetch)
            return Cached(row.data, row.fetched_at, from_cache=True)

        action = f"{kind}:{scope}" if scope else kind
        try:
            data = to_plain(await self._gateway.call(user_id, action, fetch))
        except (LKUnavailableError, SessionExpiredError) as exc:
            if row is None:
                raise PersonalDataError(str(exc)) from exc
            return Cached(row.data, row.fetched_at, from_cache=True, stale=True, error=str(exc))

        await self._store(user_id, kind, scope, data, now)
        return Cached(data, now, from_cache=False)

    async def _store(self, user_id: int, kind: str, scope: str, data: Any, now: datetime) -> None:
        stmt = insert(PersonalCache).values(user_id=user_id, kind=kind, scope=scope, data=data, fetched_at=now)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "kind", "scope"],
            set_={"data": stmt.excluded.data, "fetched_at": stmt.excluded.fetched_at},
        )
        async with self._sessionmaker() as session:
            await session.execute(stmt)
            if kind == "profile" and not scope and isinstance(data, dict):
                await session.execute(_profile_upsert(user_id, data, now))
            if kind in HISTORY_KINDS:
                digest = data_hash(data)
                last = await session.scalar(
                    select(PersonalHistory.data_hash)
                    .where(
                        PersonalHistory.user_id == user_id,
                        PersonalHistory.kind == kind,
                        PersonalHistory.scope == scope,
                    )
                    .order_by(PersonalHistory.captured_at.desc(), PersonalHistory.id.desc())
                    .limit(1)
                )
                if last != digest:
                    session.add(
                        PersonalHistory(
                            user_id=user_id, kind=kind, scope=scope, data=data, data_hash=digest, captured_at=now
                        )
                    )
            await session.commit()

    def _refresh_in_background(
        self, user_id: int, kind: str, scope: str, fetch: Callable[[LKClient], Awaitable[Any]]
    ) -> None:
        key = (user_id, kind, scope)
        if key in self._background and not self._background[key].done():
            return

        async def run() -> None:
            try:
                await self.get(user_id, kind, fetch, scope=scope, refresh=True)
            except Exception as exc:  # noqa: BLE001 — фоновое обновление: ошибка уже в журнале ЛК, кэш остаётся
                log.info("фоновое обновление %s для пользователя %s не удалось: %s", kind, user_id, exc)

        self._background[key] = asyncio.get_running_loop().create_task(run())

    async def student_group(self, user_id: int) -> str | None:
        """Учебная группа пользователя без похода в ЛК: student_profiles, иначе последний срез профиля в кэше."""
        async with self._sessionmaker() as session:
            group = await session.scalar(select(StudentProfile.group_name).where(StudentProfile.user_id == user_id))
            if not group:
                row = await session.get(PersonalCache, (user_id, "profile", ""))
                group = (row.data or {}).get("group") if row is not None and isinstance(row.data, dict) else None
        return (group or "").strip() or None

    async def history(self, user_id: int, kind: str, *, scope: str = "", limit: int = 10) -> list[PersonalHistory]:
        stmt = (
            select(PersonalHistory)
            .where(PersonalHistory.user_id == user_id, PersonalHistory.kind == kind, PersonalHistory.scope == scope)
            .order_by(PersonalHistory.captured_at.desc(), PersonalHistory.id.desc())
            .limit(limit)
        )
        async with self._sessionmaker() as session:
            return list(await session.scalars(stmt))

    async def remember_notifications(self, user_id: int, kind: str, items: list[dict[str, Any]]) -> set[str]:
        """Записывает уведомления/объявления; возвращает id тех, что пришли впервые."""
        rows = [
            {
                "user_id": user_id,
                "kind": kind,
                "external_id": str(item.get("id") or data_hash(item)[:32]),
                "title": item.get("title") or "",
                "body": item.get("text") or item.get("content") or "",
                "published": " ".join(x for x in (item.get("date"), item.get("time")) if x),
            }
            for item in items
        ]
        if not rows:
            return set()
        stmt = (
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["user_id", "kind", "external_id"])
            .returning(Notification.external_id)
        )
        async with self._sessionmaker() as session:
            new_ids = set(await session.scalars(stmt))
            await session.commit()
        return new_ids
