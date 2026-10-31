# Офлайн-тесты чистых функций: даты, расписания, поиск преподавателя, сравнение срезов, представления, ключи.

from __future__ import annotations

from datetime import date

import pytest
from cryptography.fernet import Fernet

from mospolytech_mcp.crypto import SecretKeyMissingError, TokenCipher, hash_api_key, new_api_key
from mospolytech_mcp.identity import bearer_key
from mospolytech_mcp.personal import diff, to_plain
from mospolytech_mcp.lk_api.models import DialogueMessage
from mospolytech_mcp.schedule_format import (
    DateParseError,
    format_schedule,
    lessons_from_open_schedule,
    merge_by_groups,
    parse_date,
)
from mospolytech_mcp.teachers import match_teachers
from mospolytech_mcp.lk_api.models import html_to_text
from mospolytech_mcp.views import current_semester, in_date_interval, my_schedule_view, performance_view, profile_view

from .fakes import semester, session_file

TODAY = date(2026, 10, 7)  # среда


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("сегодня", date(2026, 10, 7)),
        ("Завтра", date(2026, 10, 8)),
        ("вчера", date(2026, 10, 6)),
        ("пятница", date(2026, 10, 9)),
        ("в пятницу", date(2026, 10, 9)),
        ("среда", date(2026, 10, 7)),
        ("пн", date(2026, 10, 12)),
        ("2026-12-01", date(2026, 12, 1)),
        ("01.12.2026", date(2026, 12, 1)),
        ("1.12", date(2026, 12, 1)),
    ],
)
def test_parse_date(text, expected):
    assert parse_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["когда-нибудь", "31.02", "2026-13-01"])
def test_parse_date_rejects_garbage(text):
    with pytest.raises(DateParseError):
        parse_date(text, TODAY)


def test_semester_lessons_and_week_view():
    lessons = lessons_from_open_schedule(semester("241-327"))
    assert {(x["weekday"], x["pair"], x["subject"]) for x in lessons} == {
        (2, 5, "Разработка мобильных приложений"),
        (4, 1, "Базы данных"),
    }
    week = format_schedule(lessons, is_session=False)
    assert [d["weekday"] for d in week["days"]] == ["вторник", "четверг"]
    assert week["days"][1]["lessons"][0] == {
        "pair": 1,
        "time": "9:00–10:30",
        "subject": "Базы данных",
        "type": "Практика",
        "teachers": ["Бритвина Валентина Валентиновна", "Баринова Наталья Владимировна"],
        "rooms": ["Пр 2413"],
        "location": "Прянишникова",
        "period": "01.09.2026–03.01.2027",
    }


def test_day_view_respects_lesson_period():
    lessons = lessons_from_open_schedule(semester("241-327"))
    assert len(format_schedule(lessons, is_session=False, on_date=date(2026, 9, 8))["lessons"]) == 1
    assert format_schedule(lessons, is_session=False, on_date=date(2026, 11, 3))["lessons"] == []
    assert format_schedule(lessons, is_session=False, on_date=date(2026, 9, 9))["lessons"] == []


def test_session_lessons_have_dates():
    raw = {"group": "241-327", "is_session": True, **session_file()["241-327"]}
    lessons = lessons_from_open_schedule(raw)
    assert lessons[0]["date"] == "2027-01-15" and lessons[0]["weekday"] is None
    view = format_schedule(lessons, is_session=True)
    assert view["days"][0]["weekday"] == "пятница"
    assert "period" not in view["days"][0]["lessons"][0]


def test_merge_by_groups():
    base = {"weekday": 2, "date": None, "pair": 5, "subject": "РМП", "type": "Лекция", "rooms": ["A"],
            "date_from": "2026-09-01", "date_to": "2026-11-01"}
    merged = merge_by_groups([{**base, "group": "241-328"}, {**base, "group": "241-327"}, {**base, "pair": 6, "group": "241-327"}])
    assert sorted(len(m["groups"]) for m in merged) == [1, 2]
    assert next(m for m in merged if m["pair"] == 5)["groups"] == ["241-327", "241-328"]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Васильев", ["Васильев Денис Борисович"]),
        ("васил", ["Васильев Денис Борисович", "Васильева Анна Петровна"]),
        ("Петр", ["Васильева Анна Петровна", "Семенов Пётр Ильич"]),  # не фамилия — по любому слову
        ("Ильич", ["Семенов Пётр Ильич"]),
        ("Васильев Д. Б.", ["Васильев Денис Борисович"]),
        ("Денис Борисович", ["Васильев Денис Борисович"]),
        ("Семёнов", ["Семенов Пётр Ильич"]),
        ("Иванов", []),
        ("...", []),
    ],
)
def test_match_teachers(query, expected):
    names = ["Васильев Денис Борисович", "Васильева Анна Петровна", "Семенов Пётр Ильич", "Греку Максим Васильевич"]
    assert match_teachers(query, names) == expected


def test_match_teachers_prefers_exact_full_name():
    names = ["Васильев Денис Борисович", "Васильев Денис Борисович-Петров"]
    assert match_teachers("васильев денис борисович", names) == ["Васильев Денис Борисович"]


def test_diff_keyed_lists_and_dicts():
    old = {"education": [{"id": "c1", "balance": "100", "name": "Обучение"}], "dormitory": []}
    new = {"education": [{"id": "c1", "balance": "0", "name": "Обучение"}, {"id": "c2", "name": "Доп. курс"}], "dormitory": []}
    assert diff(old, new) == [
        "education[id=c1].balance: '100' → '0'",
        "education[id=c2]: новая запись «Доп. курс»",
    ]
    assert diff(old, old) == []


def test_to_plain_drops_raw_and_trailing_underscore():
    message = DialogueMessage.from_dict({"from": "Деканат", "text": "Привет"})
    plain = to_plain([message])
    assert plain[0]["from"] == "Деканат" and "from_" not in plain[0]


def test_views():
    profile = profile_view({"surname": "Деев", "group": "241-327", "avatar": "a.png", "phone": "", "code": "09.03.01"})
    assert profile == {"surname": "Деев", "group": "241-327", "specialty_code": "09.03.01"}
    perf = performance_view([{"name": "БД", "grade": "Отлично"}, {"name": "ОС", "grade": ""}])
    assert perf["summary"] == {"Отлично": 1, "нет оценки": 1}
    schedule = {"2026-10-08": {"lessons": [{"name": "БД", "time_interval": "9:00"}]}, "2026-10-09": {"lessons": []}}
    view = my_schedule_view(schedule, date(2026, 10, 8))
    assert [d["day"] for d in view["days"]] == ["2026-10-08"] and view["days"][0]["weekday"] == "четверг"


@pytest.mark.parametrize(
    ("course", "today", "expected"),
    [("3", date(2026, 10, 7), 5), ("3", date(2027, 1, 20), 5), ("3", date(2027, 3, 1), 6), ("", date(2026, 10, 1), 1)],
)
def test_current_semester(course, today, expected):
    assert current_semester(course, today) == expected


def test_token_cipher_and_keys():
    cipher = TokenCipher(Fernet.generate_key().decode())
    assert cipher.decrypt(cipher.encrypt("legacy-token")) == "legacy-token"
    assert cipher.encrypt("") == ""
    with pytest.raises(SecretKeyMissingError):
        TokenCipher(None).encrypt("x")
    with pytest.raises(ValueError, match="MCP_SECRET_KEY"):
        TokenCipher(Fernet.generate_key().decode()).decrypt(cipher.encrypt("x"))

    key = new_api_key()
    assert key.startswith("mpk_") and len(hash_api_key(key)) == 64 and hash_api_key(key) != hash_api_key(new_api_key())


def test_bearer_key():
    assert bearer_key({"authorization": "Bearer mpk_abc"}) == "mpk_abc"
    assert bearer_key({"Authorization": "bearer mpk_abc"}) == "mpk_abc"
    assert bearer_key({"authorization": "Bearer something-else"}) is None
    assert bearer_key(None) is None


@pytest.mark.parametrize(
    ("interval", "day", "expected"),
    [
        ("01 Сен - 01 Ноя", date(2026, 10, 7), True),
        ("01 Сен - 01 Ноя", date(2026, 11, 2), False),
        ("02 Ноя - 03 Янв", date(2027, 1, 2), True),  # через Новый год
        ("02 Ноя - 03 Янв", date(2026, 12, 31), True),
        ("09 Фев - 31 Мая", date(2027, 3, 1), True),
        ("09 Фев - 31 Мая", date(2026, 10, 7), False),
        ("15 Янв", date(2027, 1, 15), True),
        ("", date(2026, 10, 7), True),
    ],
)
def test_in_date_interval(interval, day, expected):
    assert in_date_interval(interval, day) is expected


def test_lk_schedule_view_weekday_names():
    schedule = {"Tuesday": {"lessons": [{"name": "РМП", "date_interval": "01 Сен - 01 Ноя"}]}, "Thursday": {"lessons": []}}
    view = my_schedule_view(schedule, date(2026, 10, 6))
    assert view["days"] == [{"day": "Tuesday", "weekday": "вторник", "lessons": [{"subject": "РМП", "period": "01 Сен - 01 Ноя"}]}]
    assert my_schedule_view(schedule, date(2026, 11, 3))["days"][0]["lessons"] == []


def test_html_to_text_and_message_fields():
    assert html_to_text("<p>Добрый&nbsp;день</p><p>жду</p>") == "Добрый день\nжду"
    message = DialogueMessage.from_dict({"author_name": "Деканат", "msg_id": "9", "html": "<b>Привет</b>"})
    assert (message.from_, message.text, message.id) == ("Деканат", "Привет", "9")


def test_messages_view_takes_latest():
    from mospolytech_mcp.views import messages_view

    newest_first = [{"text": f"m{i}", "datetime": f"2026-10-0{i} 10:00:00"} for i in (3, 2, 1)]
    view = messages_view(newest_first, 2)
    assert [m["text"] for m in view["messages"]] == ["m2", "m3"] and view["total"] == 3
