# Интеграционные тесты открытых данных: список групп, расписание группы и преподавателя, кэш и откат на него.

from __future__ import annotations

from datetime import date, timedelta

import pytest
from mcp import Client
from sqlalchemy import func, select

from mospolytech_mcp.db import LKAccessLog, ScheduleCache
from mospolytech_mcp.server import create_server

from .helpers import ToolFailed, call


def next_weekday(weekday: int) -> date:
    """Ближайшая дата с данным днём недели (1 — понедельник) в пределах 01.09–01.11.2026."""
    d = date(2026, 9, 1)
    return d + timedelta(days=(weekday - d.isoweekday()) % 7)


async def test_list_groups_filter_and_cache(services, fake_open):
    async with Client(create_server(services)) as client:
        everything = await call(client, "list_groups")
        assert everything == {"count": 3, "groups": ["221-111", "241-327", "241-328"]}
        found = await call(client, "list_groups", query="241-3")
        assert found["groups"] == ["241-327", "241-328"]
    # второй вызов — из кэша, источник опрошен один раз
    assert fake_open.calls.count(("groups",)) == 1


async def test_group_schedule_week_and_day(services):
    async with Client(create_server(services)) as client:
        week = await call(client, "group_schedule", group="241-327")
        assert week["kind"] == "семестр"
        assert [d["weekday"] for d in week["days"]] == ["вторник", "четверг"]
        tuesday = week["days"][0]["lessons"][0]
        assert tuesday["pair"] == 5 and tuesday["time"] == "16:10–17:40"
        assert tuesday["period"] == "01.09.2026–01.11.2026"

        day = await call(client, "group_schedule", group="241-327", date=next_weekday(4).isoformat())
        assert day["weekday"] == "четверг"
        assert [x["subject"] for x in day["lessons"]] == ["Базы данных"]
        assert day["lessons"][0]["teachers"] == ["Бритвина Валентина Валентиновна", "Баринова Наталья Владимировна"]

        # после 01.11 мобильная разработка заканчивается — во вторник пусто
        late = await call(client, "group_schedule", group="241-327", date="2026-11-10")
        assert late["lessons"] == []


async def test_group_schedule_unknown_group_hint(services):
    async with Client(create_server(services)) as client:
        with pytest.raises(ToolFailed, match="241-327"):
            await call(client, "group_schedule", group="241-999")
        with pytest.raises(ToolFailed, match="не понял дату"):
            await call(client, "group_schedule", group="241-327", date="когда-нибудь")


async def test_group_schedule_falls_back_to_stale_cache(services, fake_open, sessionmaker):
    async with Client(create_server(services)) as client:
        fresh = await call(client, "group_schedule", group="241-327")
        assert fresh["source"] == "источник"
        # кэш устарел, а источник лёг — отдаём кэш с пометкой (ТН-001)
        async with sessionmaker() as session:
            row = await session.get(ScheduleCache, ("241-327", False))
            row.fetched_at -= timedelta(days=2)
            await session.commit()
        fake_open.down = True
        stale = await call(client, "group_schedule", group="241-327")
        assert stale["source"] == "кэш" and stale["stale"] is True
        assert stale["days"] == fresh["days"]
        # для группы без кэша — понятная ошибка, а не падение сервера (ТН-002)
        with pytest.raises(ToolFailed, match="недоступно"):
            await call(client, "group_schedule", group="221-111")
        assert (await call(client, "list_groups"))["count"] == 3


async def test_teacher_schedule_from_index(services, sessionmaker):
    async with Client(create_server(services)) as client:
        with pytest.raises(ToolFailed, match="ещё не собран"):
            await call(client, "teacher_schedule", teacher="Васильев")

        state = await services.teachers.rebuild()
        assert state["semester_ok"] == 3 and state["session_groups"] == 1

        # «Васил» подходит двоим — просим уточнить
        many = await call(client, "teacher_schedule", teacher="Васил")
        assert many["matches"] == ["Васильев Денис Борисович", "Васильева Анна Петровна"]

        # точная фамилия — без однофамильцев с другим окончанием
        assert (await call(client, "teacher_schedule", teacher="Васильев"))["teacher"] == "Васильев Денис Борисович"
        one = await call(client, "teacher_schedule", teacher="васильев д б")
        assert one["teacher"] == "Васильев Денис Борисович"
        lesson = one["days"][0]["lessons"][0]
        # поток двух групп — одно занятие со списком групп
        assert lesson["groups"] == ["241-327", "241-328"]

        exam = await call(client, "teacher_schedule", teacher="Бритвина", session=True)
        assert exam["days"][0]["date"] == "2027-01-15"
        assert exam["days"][0]["lessons"][0]["type"] == "Экзамен"

    # открытые данные не пишутся в журнал обращений к ЛК (ТЭ-001)
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(LKAccessLog)) == 0


async def test_teacher_index_keeps_old_data_when_source_is_down(services, fake_open):
    await services.teachers.rebuild()
    fake_open.down = True
    with pytest.raises(ConnectionError):
        await services.teachers.rebuild()
    assert await services.teachers.find("Бритвина") == ["Бритвина Валентина Валентиновна"]
