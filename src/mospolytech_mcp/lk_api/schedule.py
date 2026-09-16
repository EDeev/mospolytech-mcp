# Расписание пользователя, группы и преподавателя через ЛК-сессию (ФЛК-002).

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from .models import Schedule, schedule_from_dict


@dataclass
class ScheduleRange:
    mode: str | None = None
    from_: str | None = None
    to: str | None = None

    def as_query(self) -> str:
        parts = []
        if self.mode:
            parts.append(f"mode={quote(self.mode)}")
        if self.from_:
            parts.append(f"from={quote(self.from_)}")
        if self.to:
            parts.append(f"to={quote(self.to)}")
        return "&".join(parts)


class ScheduleMixin:
    async def get_my_schedule(self, r: ScheduleRange | None = None) -> Schedule:
        query = "getSchedule"
        if r is not None and (extra := r.as_query()):
            query += "&" + extra
        raw = await self.lk_get(query)  # type: ignore[attr-defined]
        return schedule_from_dict(raw or {})

    async def get_session_schedule(self, r: ScheduleRange | None = None) -> Schedule:
        query = "getSchedule&session=1"
        if r is not None and (extra := r.as_query()):
            query += "&" + extra
        raw = await self.lk_get(query)  # type: ignore[attr-defined]
        return schedule_from_dict(raw or {})

    async def get_group_schedule(
        self, group: str, r: ScheduleRange | None = None
    ) -> Schedule:
        query = f"getSchedule&group={quote(group)}"
        if r is not None and (extra := r.as_query()):
            query += "&" + extra
        raw = await self.lk_get(query)  # type: ignore[attr-defined]
        return schedule_from_dict(raw or {})

    async def get_teacher_schedule(
        self, fio: str, *, session: bool = False, r: ScheduleRange | None = None
    ) -> Schedule:
        query = f"getScheduleTeacher&fio={quote(fio)}"
        if session:
            query += "&session=1"
        if r is not None and (extra := r.as_query()):
            query += "&" + extra
        raw = await self.lk_get(query)  # type: ignore[attr-defined]
        return schedule_from_dict(raw or {})
