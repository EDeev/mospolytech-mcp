# Ответы инструментов ЛК: из полных моделей lk_api — только то, что нужно LLM, с понятными именами полей.

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

from .schedule_format import WEEKDAYS

_PROFILE_FIELDS = {
    "surname": "surname",
    "name": "name",
    "patronymic": "patronymic",
    "group": "group",
    "course": "course",
    "faculty": "faculty",
    "specialty": "specialty",
    "specialization": "specialization",
    "code": "specialty_code",
    "education_form": "education_form",
    "finance": "finance",
    "degree_level": "degree_level",
    "degree_length": "degree_length",
    "enter_year": "enter_year",
    "status": "status",
    "user_status": "user_status",
    "email": "email",
    "phone": "phone",
    "birthday": "birthday",
    "orders": "orders",
    "pass_expire_date": "pass_expire_date",
    "vacation_start": "vacation_start",
    "vacation_end": "vacation_end",
}


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v not in ("", None, [], {})}


def profile_view(user: dict[str, Any]) -> dict[str, Any]:
    return _compact({out: user.get(src) for src, out in _PROFILE_FIELDS.items()})


def current_semester(course: Any, today: date | None = None) -> int:
    """Номер семестра по курсу: сентябрь–январь — нечётный, февраль–август — чётный."""
    today = today or date.today()
    try:
        n = int(str(course).strip())
    except ValueError:
        n = 1
    n = max(n, 1)
    return n * 2 - 1 if today.month >= 9 or today.month == 1 else n * 2


def performance_view(records: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        _compact(
            {
                "subject": r.get("name"),
                "type": r.get("exam_type"),
                "grade": r.get("grade"),
                "date": r.get("exam_date"),
                "teacher": r.get("teacher"),
                "chair": r.get("chair"),
                "document": r.get("doc_type"),
            }
        )
        for r in records
    ]
    grades = Counter(r.get("grade") or "нет оценки" for r in records)
    return {"records": items, "summary": dict(grades.most_common())}


def _contract_view(c: dict[str, Any], kind: str) -> dict[str, Any]:
    payments = c.get("payments") or []
    return _compact(
        {
            "kind": kind,
            "number": c.get("number"),
            "name": c.get("name"),
            "status": c.get("status_1c"),
            "sum": c.get("sum"),
            "balance": c.get("balance"),
            "balance_date": c.get("balance_curr_date"),
            "last_payment_date": c.get("last_payment_date"),
            "start_date": c.get("start_date"),
            "end_date_plan": c.get("end_date_plan"),
            "can_sign": c.get("can_sign") or None,
            "payments": payments[-10:],
            "payments_total": len(payments) if len(payments) > 10 else None,
            "agreements": [
                _compact({"name": a.get("name"), "date": a.get("date"), "status": a.get("status")})
                for a in c.get("agreements") or []
            ],
        }
    )


def payments_view(payments: dict[str, Any]) -> dict[str, Any]:
    contracts = [_contract_view(c, "обучение") for c in payments.get("education") or []]
    contracts += [_contract_view(c, "общежитие") for c in payments.get("dormitory") or []]
    return {"contracts": contracts}


def requests_view(requests: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "requests": [
            _compact(
                {
                    "number": r.get("num"),
                    "subject": r.get("subject"),
                    "status": r.get("status"),
                    "created": r.get("created"),
                    "status_updated": r.get("status_update"),
                    "department": r.get("response_div"),
                    "contact": r.get("response_contact"),
                    "comment": r.get("comment"),
                    "files": [f.get("fname") for f in r.get("files_output") or []],
                }
            )
            for r in requests
        ]
    }


def dialogs_view(dialogs: list[dict[str, Any]]) -> dict[str, Any]:
    out = []
    for d in dialogs:
        last = d.get("last_message") or {}
        opponent = d.get("opponent") or {}
        out.append(
            _compact(
                {
                    "dialog_id": d.get("id"),
                    "subject": d.get("subject"),
                    "with": opponent.get("name"),
                    "with_status": opponent.get("status"),
                    "last_message": _compact(
                        {"text": last.get("text"), "at": last.get("datetime"), "read": last.get("readed")}
                    ),
                }
            )
        )
    return {"dialogs": out}


def messages_view(messages: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    """Последние limit сообщений, от старых к новым. ЛК отдаёт их от новых к старым — сортируем по времени."""
    ordered = sorted(messages, key=lambda m: m.get("datetime") or "")
    tail = ordered[-limit:] if limit > 0 else ordered
    return {
        "messages": [
            _compact({"from": m.get("from"), "text": m.get("text"), "at": m.get("datetime"), "read": m.get("readed")})
            for m in tail
        ],
        "total": len(messages),
    }


_EN_WEEKDAYS = {name: i for i, name in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], start=1
)}
_RU_MONTHS = {m: i for i, m in enumerate(
    ["янв", "фев", "мар", "апр", "май", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"], start=1
)}
_RU_MONTHS["мая"] = 5


def _key_date(key: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(key, fmt).date()
        except ValueError:
            pass
    return None


def _key_weekday(key: str) -> int | None:
    """День недели ключа расписания ЛК: «Monday» (так отвечает getSchedule) или «1»."""
    if key.lower() in _EN_WEEKDAYS:
        return _EN_WEEKDAYS[key.lower()]
    if key.isdigit() and 1 <= int(key) <= 7:
        return int(key)
    return None


def _day_month(text: str) -> tuple[int, int] | None:
    parts = text.strip().split()
    if len(parts) < 2 or not parts[0].isdigit():
        return None
    month = _RU_MONTHS.get(parts[1].lower()[:3]) or _RU_MONTHS.get(parts[1].lower())
    return (int(parts[0]), month) if month else None


def in_date_interval(interval: str, day: date) -> bool:
    """«01 Сен - 01 Ноя» (период занятия в ЛК, без года) содержит day? Неразборчивый период — считаем, что да."""
    ends = [x for x in interval.replace("–", "-").split("-") if x.strip()]
    parsed = [_day_month(x) for x in ends]
    if not parsed or any(p is None for p in parsed):
        return True
    (d1, m1), (d2, m2) = parsed[0], parsed[-1]
    for start_year in (day.year - 1, day.year):
        end_year = start_year if (m2, d2) >= (m1, d1) else start_year + 1
        try:
            if date(start_year, m1, d1) <= day <= date(end_year, m2, d2):
                return True
        except ValueError:
            return True
    return False


def _lk_lesson(lesson: dict[str, Any]) -> dict[str, Any]:
    return _compact(
        {
            "time": lesson.get("time_interval"),
            "subject": lesson.get("name"),
            "teachers": lesson.get("teachers"),
            "rooms": lesson.get("rooms"),
            "place": lesson.get("place"),
            "period": lesson.get("date_interval"),
            "link": lesson.get("link"),
        }
    )


def my_schedule_view(schedule: dict[str, Any], on_date: date | None) -> dict[str, Any]:
    """Расписание ЛК: ключи дней — «Monday»…, даты или номера дней; с date — только этот день и занятия,
    чей период его включает."""
    days = []
    for key, day in schedule.items():
        raw_lessons = (day or {}).get("lessons") or []
        key_date = _key_date(key)
        weekday = key_date.isoweekday() if key_date else _key_weekday(key)
        if on_date is not None:
            if key_date is not None and key_date != on_date:
                continue
            if key_date is None and weekday is not None and weekday != on_date.isoweekday():
                continue
            raw_lessons = [x for x in raw_lessons if in_date_interval(x.get("date_interval") or "", on_date)]
        entry: dict[str, Any] = {"day": key}
        if weekday is not None:
            entry["weekday"] = WEEKDAYS[weekday - 1]
        entry["lessons"] = [_lk_lesson(x) for x in raw_lessons]
        days.append(entry)
    result: dict[str, Any] = {"days": days}
    if on_date is not None:
        result["date"] = on_date.isoformat()
        result["weekday"] = WEEKDAYS[on_date.isoweekday() - 1]
    return result
