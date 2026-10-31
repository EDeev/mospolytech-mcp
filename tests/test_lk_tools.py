# Интеграционные тесты личного кабинета: вход, данные от имени пользователя, журнал, история, откат на кэш.

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from mcp import Client
from sqlalchemy import func, select, update

from mospolytech_mcp.db import (
    ApiKey, LKAccessLog, Notification, PersonalCache, PersonalHistory, StudentProfile, TrackedGroup, User,
    UserSession,
)
from mospolytech_mcp.server import create_server

from .fakes import DIALOG_ID, FakeLK
from .helpers import ToolFailed, call


def connect(services) -> Client:
    # вход «в рамках подключения» живёт только в протоколе с сессиями (до 2026-07-28) и в stdio
    return Client(create_server(services), mode="legacy")


async def login(client: Client) -> dict:
    return await call(client, "lk_login", login=FakeLK.LOGIN, password=FakeLK.PASSWORD)


async def test_tools_require_login(services):
    async with connect(services) as client:
        with pytest.raises(ToolFailed, match="lk_login"):
            await call(client, "my_profile")


async def test_login_wrong_password_is_logged(services, sessionmaker):
    async with connect(services) as client:
        with pytest.raises(ToolFailed, match="неверный логин или пароль"):
            await call(client, "lk_login", login=FakeLK.LOGIN, password="nope")
    async with sessionmaker() as session:
        entry = await session.scalar(select(LKAccessLog))
        assert (entry.action, entry.status, entry.login, entry.user_id) == ("login", "denied", FakeLK.LOGIN, None)
        assert await session.scalar(select(func.count()).select_from(User)) == 0


async def test_login_stores_encrypted_tokens_and_key_hash(services, sessionmaker):
    async with connect(services) as client:
        result = await login(client)
        assert result["user"] == "Деев Егор Викторович" and result["group"] == "241-327"
        assert result["api_key"].startswith("mpk_")
        profile = await call(client, "my_profile")
        assert profile["group"] == "241-327" and "avatar" not in profile

    async with sessionmaker() as session:
        stored = await session.scalar(select(UserSession))
        assert "legacy-token" not in stored.token_enc and stored.token_enc
        key = await session.scalar(select(ApiKey))
        assert result["api_key"] not in key.key_hash and len(key.key_hash) == 64


async def test_modern_protocol_needs_personal_key(services):
    # в протоколе 2026-07-28 нет сессий: после lk_login клиент должен передавать ключ в заголовке
    async with Client(create_server(services)) as client:
        assert (await login(client))["api_key"].startswith("mpk_")
        with pytest.raises(ToolFailed, match="Authorization: Bearer"):
            await call(client, "my_profile")


async def test_bearer_key_identifies_user(services):
    async with connect(services) as client:
        key = (await login(client))["api_key"]

    class Ctx:
        headers = {"authorization": f"Bearer {key}"}
        session = object()

    user_id = await services.identity.require(Ctx())
    assert (await services.auth.get_user(user_id)).login == FakeLK.LOGIN

    Ctx.headers = {"authorization": "Bearer mpk_wrong"}
    with pytest.raises(Exception, match="недействителен"):
        await services.identity.require(Ctx())


async def test_personal_data_cache_and_access_log(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        # refresh=true — личное расписание из ЛК
        schedule = await call(client, "my_schedule", refresh=True)
        assert [d["weekday"] for d in schedule["days"]] == ["вторник", "четверг"]
        # без refresh — быстрый путь: группа из профиля (первый раз профиль берётся из ЛК и попадает в
        # student_profiles), расписание — открытое расписание группы, без ЛК
        fast = await call(client, "my_schedule", date="2026-10-08")  # четверг
        assert fast["group"] == "241-327" and "без входа в ЛК" in fast["note"]
        assert fast["weekday"] == "четверг" and "lessons" in fast
        again = await call(client, "my_schedule", date="2026-11-10")
        assert again["group"] == "241-327"

        payments = await call(client, "my_payments")
        assert payments["contracts"][0]["kind"] == "обучение"
        requests = await call(client, "my_requests")
        assert requests["requests"][0]["status"] == "Готово"

    async with sessionmaker() as session:
        actions = list(await session.scalars(select(LKAccessLog.action).order_by(LKAccessLog.id)))
        # профиль — один раз (дальше группа из student_profiles), расписание быстрым путём в ЛК не ходит
        assert actions == ["login", "schedule", "profile", "payments", "requests"]
        assert await session.scalar(select(func.count()).select_from(PersonalCache)) == 4
        profile = await session.scalar(select(StudentProfile))
        assert profile.group_name == "241-327" and profile.course == 3 and profile.surname == "Деев"


async def test_performance_history_and_changes(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        first = await call(client, "my_performance", semester=5)
        assert first["summary"] == {"Хорошо": 1, "Зачтено": 1}
        await call(client, "my_performance", semester=5, refresh=True)  # без изменений — новой строки нет
        fake_lk.grade = "Отлично"
        second = await call(client, "my_performance", semester=5, refresh=True)
        assert second["records"][0]["grade"] == "Отлично"

        changes = await call(client, "my_changes", kind="performance", semester=5)
        assert changes["timeline"][0]["changes"] == ["[id=p1].grade: 'Хорошо' → 'Отлично'"]
        assert changes["timeline"][1]["changes"] == ["первый сохранённый срез"]

        # semester=0 — текущий по курсу из профиля
        current = await call(client, "my_performance")
        assert current["semester"] in (5, 6)

    async with sessionmaker() as session:
        rows = await session.scalar(
            select(func.count()).select_from(PersonalHistory).where(PersonalHistory.scope == "5")
        )
        assert rows == 2


async def test_notifications_new_flag_and_dedup(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        first = await call(client, "my_notifications")
        assert first["notifications"][0]["new"] is True and first["alerts"][0]["new"] is True
        assert first["counts"] == {"notifications": 1, "alerts": 1, "new": 2}
        assert (await call(client, "my_notifications", only_new=True))["notifications"] == []

        fake_lk.notifications.append({"id": "n2", "title": "Новая ведомость", "text": "БД"})
        fresh = await call(client, "my_notifications", only_new=True)
        assert [n["id"] for n in fresh["notifications"]] == ["n2"] and fresh["alerts"] == []

    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(Notification)) == 3


async def test_lk_down_returns_stale_cache(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        await call(client, "list_dialogs")
        fake_lk.down = True
        stale = await call(client, "list_dialogs", refresh=True)
        assert stale["stale"] is True and stale["dialogs"][0]["with"] == "Васильев Д. Б."
        with pytest.raises(ToolFailed, match="502"):
            await call(client, "my_requests")

    async with sessionmaker() as session:
        statuses = list(await session.scalars(select(LKAccessLog.status).order_by(LKAccessLog.id)))
        assert statuses == ["ok", "ok", "error", "error"]


async def test_expired_profile_served_from_cache_and_refreshed_in_background(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        await call(client, "my_profile")
        old = datetime.now(UTC) - timedelta(days=2)
        async with sessionmaker() as session:
            await session.execute(update(PersonalCache).where(PersonalCache.kind == "profile").values(fetched_at=old))
            await session.commit()

        profile = await call(client, "my_profile")  # просрочен — сразу из кэша, ЛК — в фоне
        assert profile["source"] == "кэш" and profile["group"] == "241-327"
        for _ in range(50):
            async with sessionmaker() as session:
                fetched = await session.scalar(select(PersonalCache.fetched_at).where(PersonalCache.kind == "profile"))
            if fetched > old:
                break
            await asyncio.sleep(0.05)
        assert fetched > old

    async with sessionmaker() as session:
        actions = list(await session.scalars(select(LKAccessLog.action).order_by(LKAccessLog.id)))
        assert actions == ["login", "profile", "profile"]


async def test_expired_lk_session_asks_to_login_again(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        fake_lk.token = "rotated"  # ЛК перестал принимать наш токен
        with pytest.raises(ToolFailed, match="истекла"):
            await call(client, "group_chat")
        with pytest.raises(ToolFailed, match="нет активной сессии"):
            await call(client, "group_chat")
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(UserSession)) == 0


async def test_jwt_is_refreshed_periodically(services, sessionmaker, fake_lk):
    async with connect(services) as client:
        await login(client)
        async with sessionmaker() as session:
            await session.execute(update(UserSession).values(refreshed_at=datetime.now(UTC) - timedelta(hours=1)))
            await session.commit()
        await call(client, "group_chat")
    assert any(r.startswith("POST /auth/token/reissue") for r in fake_lk.requests)
    async with sessionmaker() as session:
        stored = await session.scalar(select(UserSession))
        assert datetime.now(UTC) - stored.refreshed_at < timedelta(minutes=1)
        actions = list(await session.scalars(select(LKAccessLog.action).order_by(LKAccessLog.id)))
        assert actions == ["login", "token_refresh", "group_chat"]


async def test_dialog_messages_and_send(services, fake_lk):
    async with connect(services) as client:
        await login(client)
        messages = await call(client, "dialog_messages", dialog_id=DIALOG_ID, limit=2)
        assert messages["total"] == 5 and [m["text"] for m in messages["messages"]] == ["сообщение 3", "сообщение 4"]
        assert messages["messages"][0]["from"] == "Васильев Д. Б."
        sent = await call(client, "send_message", dialog_id=DIALOG_ID, text="Отправил черновик")
        assert sent["status"] == "отправлено"
        chat = await call(client, "group_chat")
        assert chat["link"] == "https://t.me/+group241327"
    assert fake_lk.sent == [{"to_dialogue": DIALOG_ID, "text": "Отправил черновик"}]


async def test_send_group_message(services, fake_lk):
    async with connect(services) as client:
        await login(client)
        own = await call(client, "send_group_message", text="Пара перенесена")
        assert own["group"] == "241-327"
        other = await call(client, "send_group_message", text="Привет", group="241-328")
        assert other["status"] == "отправлено"
        with pytest.raises(ToolFailed, match="пустое"):
            await call(client, "send_group_message", text="  ")
    assert fake_lk.sent == [{"to_group": "241-327", "text": "Пара перенесена"}, {"to_group": "241-328", "text": "Привет"}]


async def test_bad_request_does_not_drop_session(services, sessionmaker, fake_lk):
    # ЛК отвечает 400 и на кривой запрос — сессию при этом терять нельзя
    async with connect(services) as client:
        await login(client)
        bad = await services.gateway.call(1, "probe", lambda c: c.lk_get("getProfile"))
        assert bad is None  # неизвестный запрос подделка отдаёт как null
        with pytest.raises(Exception, match="400"):
            await services.gateway.call(1, "send_message", lambda c: c.lk_post_form("newMessage=1", {"id": "x"}))
        assert (await call(client, "group_chat"))["link"]
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(UserSession)) == 1


async def test_tracked_groups_of_logged_in_user(services, sessionmaker):
    async with connect(services) as client:
        await login(client)
        assert await call(client, "add_tracked_group", group="241-328") == "группа 241-328 добавлена в отслеживаемые"
        assert await call(client, "add_tracked_group", group="241-328") == "группа 241-328 уже отслеживается"
        with pytest.raises(ToolFailed, match="нет в списке"):
            await call(client, "add_tracked_group", group="999-999")
        assert await call(client, "list_tracked_groups") == ["241-328"]
        async with sessionmaker() as session:
            user_id = await session.scalar(select(User.id).where(User.login == FakeLK.LOGIN))
            rows = (await session.execute(select(TrackedGroup.user_id, TrackedGroup.user_login))).all()
        assert rows == [(user_id, FakeLK.LOGIN)]  # привязка — по id пользователя, логин — для совместимости
        day = await call(client, "tracked_schedule", date="2026-09-01")  # вторник
        assert day["groups"][0]["lessons"][0]["subject"] == "Разработка мобильных приложений"
        assert await call(client, "remove_tracked_group", group="241-328") == "группа 241-328 больше не отслеживается"


async def test_logout_revokes_keys(services, sessionmaker):
    async with connect(services) as client:
        await login(client)
        await login(client)  # второе устройство — второй ключ
        assert (await call(client, "lk_logout"))["revoked_keys"] == 2
        with pytest.raises(ToolFailed, match="lk_login"):
            await call(client, "my_profile")
    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(ApiKey).where(ApiKey.revoked_at.is_(None))) == 0


async def test_auto_relogin_when_lk_rejects_session(settings, sessionmaker, fake_open, fake_lk):
    # личный сервер с LK_AUTO_RELOGIN: ЛК отверг сессию — сервер сам входит заново, ключ прежний
    import dataclasses

    from mospolytech_mcp.server import build_services

    own = dataclasses.replace(settings, auto_relogin=True, lk_login=FakeLK.LOGIN, lk_password=FakeLK.PASSWORD)
    services = build_services(own, sessionmaker, mode="http", open_client=fake_open, lk_factory=fake_lk.factory)
    async with connect(services) as client:
        await login(client)
        fake_lk.token = "rotated"  # ЛК выдаст при входе уже новый токен
        assert (await call(client, "group_chat"))["link"]
        assert (await call(client, "my_requests", refresh=True))["requests"]
    async with sessionmaker() as session:
        actions = list(await session.scalars(select(LKAccessLog.action + ":" + LKAccessLog.status).order_by(LKAccessLog.id)))
        assert actions == ["login:ok", "group_chat:expired", "relogin:ok", "group_chat:ok", "requests:ok"]
        assert await session.scalar(select(func.count()).select_from(ApiKey)) == 1  # нового ключа не выдано


async def test_no_auto_relogin_without_flag(services, fake_lk):
    async with connect(services) as client:
        await login(client)
        fake_lk.token = "rotated"
        with pytest.raises(ToolFailed, match="истекла"):
            await call(client, "group_chat")
