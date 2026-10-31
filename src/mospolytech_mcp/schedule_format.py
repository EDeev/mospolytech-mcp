# Приведение расписаний к единому виду для LLM: плоский список занятий, фильтр по дате, понятные даты.

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

PAIR_TIMES = {
    1: "9:00–10:30",
    2: "10:40–12:10",
    3: "12:20–13:50",
    4: "14:30–16:00",
    5: "16:10–17:40",
    6: "17:50–19:20",
    7: "19:30–21:00",
}

WEEKDAYS = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
_WEEKDAY_FORMS = {
    "пн": 1, "понедельник": 1,
    "вт": 2, "вторник": 2,
    "ср": 3, "среда": 3, "среду": 3,
    "чт": 4, "четверг": 4,
    "пт": 5, "пятница": 5, "пятницу": 5,
    "сб": 6, "суббота": 6, "субботу": 6,
    "вс": 7, "воскресенье": 7,
}
_RELATIVE = {"позавчера": -2, "вчера": -1, "сегодня": 0, "завтра": 1, "послезавтра": 2}


class DateParseError(ValueError):
    pass


def parse_date(text: str | None, today: date | None = None) -> date | None:
    """'' → None; «сегодня», «завтра», «пятница», 2026-10-08, 08.10.2026, 08.10 → дата."""
    if text is None:
        return None
    value = text.strip().lower()
    if not value:
        return None
    today = today or date.today()
    if value in _RELATIVE:
        return today + timedelta(days=_RELATIVE[value])
    word = value.removeprefix("в ").removeprefix("во ").strip()
    if word in _WEEKDAY_FORMS:
        delta = (_WEEKDAY_FORMS[word] - today.isoweekday()) % 7
        return today + timedelta(days=delta)
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    if m := re.fullmatch(r"(\d{1,2})\.(\d{1,2})", value):
        try:
            return date(today.year, int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    raise DateParseError(
        f"не понял дату {text!r} — подойдёт «сегодня», «завтра», день недели, 2026-10-08 или 08.10.2026"
    )


def _iso(ru_date: str) -> str:
    """dd.mm.yyyy → yyyy-mm-dd."""
    d, m, y = ru_date.split(".")
    return f"{y}-{m}-{d}"


def _ru(iso_date: str) -> str:
    y, m, d = iso_date.split("-")
    return f"{d}.{m}.{y}"


def lessons_from_open_schedule(schedule: dict[str, Any]) -> list[dict[str, Any]]:
    """Расписание из mospolytech_api (сетка день → пара → занятия) → плоский список занятий.

    В семестровом расписании дни сетки идут по порядку с понедельника; в сессионном у каждого
    занятия своя дата (dates = [дата, дата]).
    """
    is_session = bool(schedule.get("is_session"))
    lessons: list[dict[str, Any]] = []
    for day_index, day in enumerate(schedule.get("grid") or []):
        for pair_index, section in enumerate(day):
            for event in section:
                date_from, date_to = (_iso(d) for d in event["dates"])
                lessons.append(
                    {
                        "weekday": None if is_session else day_index + 1,
                        "date": date_from if is_session else None,
                        "pair": pair_index + 1,
                        "subject": event["title"],
                        "type": event["type"],
                        "teachers": list(event["teachers"]),
                        "rooms": list(event["rooms"]),
                        "location": event["location"],
                        "link": event["link"],
                        "date_from": date_from,
                        "date_to": date_to,
                    }
                )
    return lessons


def _lesson_view(lesson: dict[str, Any], *, is_session: bool) -> dict[str, Any]:
    view: dict[str, Any] = {
        "pair": lesson["pair"],
        "time": PAIR_TIMES.get(lesson["pair"], ""),
        "subject": lesson["subject"],
        "type": lesson["type"],
    }
    if lesson.get("groups"):
        view["groups"] = lesson["groups"]
    if lesson.get("teachers"):
        view["teachers"] = lesson["teachers"]
    if lesson.get("rooms"):
        view["rooms"] = lesson["rooms"]
    if lesson.get("location"):
        view["location"] = lesson["location"]
    if lesson.get("link"):
        view["link"] = lesson["link"]
    if not is_session:
        view["period"] = f"{_ru(lesson['date_from'])}–{_ru(lesson['date_to'])}"
    return view


def _occurs_on(lesson: dict[str, Any], day: date, *, is_session: bool) -> bool:
    if is_session:
        return lesson["date"] == day.isoformat()
    return (
        lesson["weekday"] == day.isoweekday()
        and lesson["date_from"] <= day.isoformat() <= lesson["date_to"]
    )


def _sort_key(lesson: dict[str, Any]) -> tuple:
    return (lesson.get("date") or "", lesson.get("weekday") or 0, lesson["pair"], lesson["subject"])


def format_schedule(
    lessons: Iterable[dict[str, Any]], *, is_session: bool, on_date: date | None = None
) -> dict[str, Any]:
    """Список занятий → {"date", "weekday", "lessons"} на день или {"days": [...]} на весь период."""
    items = sorted(lessons, key=_sort_key)
    if on_date is not None:
        today = [_lesson_view(x, is_session=is_session) for x in items if _occurs_on(x, on_date, is_session=is_session)]
        return {
            "date": on_date.isoformat(),
            "weekday": WEEKDAYS[on_date.isoweekday() - 1],
            "lessons": today,
        }

    days: list[dict[str, Any]] = []
    current_key: Any = object()
    for lesson in items:
        key = lesson["date"] if is_session else lesson["weekday"]
        if key != current_key:
            current_key = key
            if is_session:
                day_date = date.fromisoformat(lesson["date"])
                days.append({"date": lesson["date"], "weekday": WEEKDAYS[day_date.isoweekday() - 1], "lessons": []})
            else:
                days.append({"weekday": WEEKDAYS[lesson["weekday"] - 1], "lessons": []})
        days[-1]["lessons"].append(_lesson_view(lesson, is_session=is_session))
    return {"days": days}


def merge_by_groups(lessons: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Одно и то же занятие у нескольких групп (поток) → одна запись со списком групп."""
    merged: dict[tuple, dict[str, Any]] = {}
    for lesson in lessons:
        key = (
            lesson.get("weekday"),
            lesson.get("date"),
            lesson["pair"],
            lesson["subject"],
            lesson["type"],
            tuple(lesson.get("rooms") or ()),
            lesson["date_from"],
            lesson["date_to"],
        )
        if key in merged:
            merged[key]["groups"].append(lesson["group"])
        else:
            merged[key] = {**lesson, "groups": [lesson["group"]]}
    for lesson in merged.values():
        lesson["groups"].sort()
    return list(merged.values())
