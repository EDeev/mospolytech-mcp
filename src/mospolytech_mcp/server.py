# MCP-сервер mospolytech-mcp: открытые данные (группы, расписания групп и преподавателей), вход в личный кабинет
# (ФЛК-001), отслеживаемые группы.

from __future__ import annotations

import argparse
import asyncio
import contextlib
import functools
import logging
import sys
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import httpx
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker

from . import __version__
from ._dotenv import load_dotenv
from .auth import (
    AccessLog,
    AuthError,
    AuthService,
    LKFactory,
    LKGateway,
    LKUnavailableError,
    NoSessionError,
    SessionExpiredError,
)
from .cache import GroupsCacheStore, ScheduleCacheStore, ScheduleNotFoundError, SourceUnavailableError
from .crypto import SecretKeyMissingError, TokenCipher
from .db import make_engine, make_sessionmaker
from .identity import Identity, InvalidKeyError, Mode, NotLoggedInError
from .lk_api import LKClient, LKError
from .open_api import OpenDataClient
from .schedule_format import DateParseError, format_schedule, merge_by_groups, parse_date
from .settings import Settings
from .teachers import IndexNotReadyError, TeacherIndex
from .tracked import TrackedGroupsStore, UnknownGroupError
from .web import add_web_routes

log = logging.getLogger(__name__)

INSTRUCTIONS = """\
Сервер даёт доступ к данным Московского Политеха.
Открытые данные (без входа): list_groups, group_schedule, teacher_schedule.
Личный кабинет: сначала lk_login(login, password) — сервер вернёт персональный ключ mpk_…; его стоит
сохранить в настройках MCP-клиента (заголовок Authorization: Bearer <ключ>), тогда входить заново не нужно.
Даты в инструментах расписания понимают «сегодня», «завтра», день недели, 2026-10-08 и 08.10.2026.
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)
MAX_TEACHER_MATCHES = 20


@dataclass
class Services:
    settings: Settings
    identity: Identity
    auth: AuthService
    gateway: LKGateway
    groups: GroupsCacheStore
    schedules: ScheduleCacheStore
    teachers: TeacherIndex
    tracked: TrackedGroupsStore


def build_services(
    settings: Settings,
    sessionmaker: async_sessionmaker,
    *,
    mode: Mode,
    open_client: OpenDataClient | None = None,
    lk_factory: LKFactory = LKClient,
) -> Services:
    open_client = open_client or OpenDataClient()
    cipher = TokenCipher(settings.secret_key)
    access_log = AccessLog(sessionmaker)
    auth = AuthService(sessionmaker, cipher, lk_factory, access_log)
    credentials = (
        {settings.lk_login: settings.lk_password}
        if (settings.auto_relogin or mode == "stdio") and settings.lk_login and settings.lk_password
        else {}
    )
    gateway = LKGateway(
        sessionmaker, cipher, lk_factory, access_log,
        refresh_interval=settings.jwt_refresh_interval, auth=auth, relogin_credentials=credentials,
    )
    groups = GroupsCacheStore(open_client, sessionmaker, ttl=settings.groups_ttl)
    schedules = ScheduleCacheStore(open_client, sessionmaker, ttl=settings.schedule_ttl)
    autologin = (settings.lk_login, settings.lk_password) if settings.lk_login and settings.lk_password else None
    return Services(
        settings=settings,
        identity=Identity(auth, mode=mode, api_key=settings.api_key, autologin=autologin),
        auth=auth,
        gateway=gateway,
        groups=groups,
        schedules=schedules,
        teachers=TeacherIndex(open_client, sessionmaker, schedules, ttl=settings.teacher_index_ttl),
        tracked=TrackedGroupsStore(sessionmaker, groups.get_groups),
    )


@contextlib.contextmanager
def friendly_errors() -> Iterator[None]:
    """Ошибки источников и авторизации → понятный ToolError; сервер продолжает работать (ТН-002)."""
    try:
        yield
    except ToolError:
        raise
    except (
        NotLoggedInError,
        InvalidKeyError,
        NoSessionError,
        SessionExpiredError,
        AuthError,
        ScheduleNotFoundError,
        SourceUnavailableError,
        IndexNotReadyError,
        DateParseError,
        UnknownGroupError,
        SecretKeyMissingError,
    ) as exc:
        raise ToolError(str(exc)) from exc
    except LKUnavailableError as exc:
        raise ToolError(f"личный кабинет не ответил: {exc}") from exc
    except (LKError, httpx.HTTPError) as exc:
        raise ToolError(f"ошибка обращения к источнику данных: {exc}") from exc
    except SQLAlchemyError as exc:
        log.exception("ошибка БД в инструменте")
        raise ToolError(f"ошибка базы данных сервера: {type(getattr(exc, "orig", None) or exc).__name__}") from exc


def create_server(svc: Services) -> MCPServer:
    @contextlib.asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        task = None
        if svc.settings.teacher_index:
            task = asyncio.create_task(svc.teachers.run_forever())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    mcp = MCPServer(
        name="mospolytech-mcp",
        title="Mospolytech MCP",
        version=__version__,
        instructions=INSTRUCTIONS,
        lifespan=lifespan,
    )

    async def user(ctx: Context) -> int:
        return await svc.identity.require(ctx)

    # ── Открытые данные (ФОД-001…003, без входа и без журнала — ТЭ-001) ──────

    @mcp.tool(annotations=READ_ONLY)
    async def list_groups(query: str = "") -> dict[str, Any]:
        """Список учебных групп Московского Политеха (ФОД-001). query — часть номера, например «241-3»."""
        with friendly_errors():
            try:
                groups = await svc.groups.get_groups()
            except Exception as exc:
                raise SourceUnavailableError(f"список групп недоступен: {exc}") from exc
        needle = query.strip().lower()
        if needle:
            groups = [g for g in groups if needle in g.lower()]
        return {"count": len(groups), "groups": groups}

    async def _check_group(group: str) -> str:
        group = group.strip()
        try:
            known = await svc.groups.get_groups()
        except Exception:
            return group  # список групп недоступен — пусть решает источник расписания
        if group in known:
            return group
        lowered = {g.lower(): g for g in known}
        if group.lower() in lowered:
            return lowered[group.lower()]
        similar = [g for g in known if g.startswith(group[:4])][:10]
        hint = f" Похожие: {', '.join(similar)}." if similar else ""
        raise ToolError(f"группы {group!r} нет в списке групп университета.{hint}")

    @mcp.tool(annotations=READ_ONLY)
    async def group_schedule(group: str, session: bool = False, date: str = "") -> dict[str, Any]:
        """Расписание учебной группы (ФОД-002): семестр или сессия (session=true).

        date — день: «сегодня», «завтра», «пятница», 2026-10-08; пусто — всё расписание по дням недели.
        """
        with friendly_errors():
            on_date = parse_date(date)
            group = await _check_group(group)
            cached = await svc.schedules.get(group, is_session=session)
        data = cached.data
        period = data.get("period") or ["", ""]
        return {
            "group": group,
            "kind": "сессия" if session else "семестр",
            "period": "–".join(p for p in period if p),
            "evening": data.get("evening", False),
            **format_schedule(data["lessons"], is_session=session, on_date=on_date),
            **cached.meta(),
        }

    @mcp.tool(annotations=READ_ONLY)
    async def teacher_schedule(teacher: str, session: bool = False, date: str = "") -> dict[str, Any]:
        """Расписание преподавателя по ФИО или его части (ФОД-003): «Васильев», «Васильев Д. Б.».

        Если подходит несколько преподавателей — вернёт список, чтобы уточнить. date — как в group_schedule.
        """
        with friendly_errors():
            on_date = parse_date(date)
            matches = await svc.teachers.find(teacher)
            if not matches:
                raise ToolError(f"преподаватель {teacher!r} не найден в расписании")
            if len(matches) > 1:
                return {
                    "matches": matches[:MAX_TEACHER_MATCHES],
                    "total": len(matches),
                    "note": "подходит несколько преподавателей — уточните ФИО",
                }
            name = matches[0]
            lessons = merge_by_groups(await svc.teachers.lessons(name, is_session=session))
            state = await svc.teachers.status() or {}
        return {
            "teacher": name,
            "kind": "сессия" if session else "семестр",
            **format_schedule(lessons, is_session=session, on_date=on_date),
            "index_built_at": state.get("built_at"),
        }

    # ── Вход и выход (ФЛК-001) ──────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True))
    async def lk_login(login: str, password: str, ctx: Context) -> dict[str, Any]:
        """Вход в личный кабинет Мосполитеха (e.mospolytech.ru) по логину и паролю.

        Пароль не сохраняется. Возвращает персональный ключ mpk_… — передавайте его в заголовке
        Authorization: Bearer <ключ>, чтобы не входить заново.
        """
        with friendly_errors():
            result = await svc.auth.login(login, password)
        svc.identity.bind(ctx, result.user_id)
        if svc.identity.mode == "stdio":
            how = "вход действует, пока запущен сервер; чтобы входить автоматически — сохраните ключ в MPU_API_KEY"
        else:
            how = (
                "сохраните ключ в настройках MCP-клиента: заголовок Authorization: Bearer <ключ>; "
                "без него вход действует только в текущем подключении"
            )
        return {
            "status": "вход выполнен",
            "user": result.full_name,
            "group": result.group,
            "api_key": result.api_key,
            "how_to_use": how,
        }

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False))
    async def lk_logout(ctx: Context) -> dict[str, Any]:
        """Выйти из личного кабинета на всех устройствах: удалить токены ЛК и отозвать все ключи mpk_…."""
        with friendly_errors():
            user_id = await user(ctx)
            revoked = await svc.auth.logout(user_id)
        svc.identity.forget(user_id)
        return {"status": "выход выполнен", "revoked_keys": revoked}

    # ── Отслеживаемые группы ────────────────────────────────────────────────

    async def _login_of(ctx: Context) -> str:
        found = await svc.auth.get_user(await user(ctx))
        if found is None:
            raise NotLoggedInError()
        return found.login

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True))
    async def add_tracked_group(ctx: Context, group: str) -> str:
        """Добавить группу в отслеживаемые (например, чужую группу, у которой бывают общие пары)."""
        with friendly_errors():
            login = await _login_of(ctx)
            added = await svc.tracked.add(login, group)
        return f"группа {group} добавлена в отслеживаемые" if added else f"группа {group} уже отслеживается"

    @mcp.tool(annotations=READ_ONLY)
    async def list_tracked_groups(ctx: Context) -> list[str]:
        """Отслеживаемые группы пользователя в порядке добавления."""
        with friendly_errors():
            return await svc.tracked.list(await _login_of(ctx))

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True, idempotent_hint=True))
    async def remove_tracked_group(ctx: Context, group: str) -> str:
        """Убрать группу из отслеживаемых."""
        with friendly_errors():
            removed = await svc.tracked.remove(await _login_of(ctx), group)
        return f"группа {group} больше не отслеживается" if removed else f"группа {group} не была в отслеживаемых"

    @mcp.tool(annotations=READ_ONLY)
    async def tracked_schedule(ctx: Context, date: str = "сегодня") -> dict[str, Any]:
        """Расписание всех отслеживаемых групп на один день (по умолчанию — на сегодня)."""
        with friendly_errors():
            on_date = parse_date(date) or parse_date("сегодня")
            groups = await svc.tracked.list(await _login_of(ctx))
        result = []
        for group in groups:
            try:
                with friendly_errors():
                    cached = await svc.schedules.get(group, is_session=False)
                result.append({"group": group, **format_schedule(cached.data["lessons"], is_session=False, on_date=on_date)})
            except ToolError as exc:
                result.append({"group": group, "error": str(exc)})
        return {"date": on_date.isoformat(), "groups": result}

    add_web_routes(mcp, svc)
    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="mospolytech-mcp")
    parser.add_argument("--http", action="store_true", help="HTTP вместо stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    load_dotenv(Path.cwd() / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx на INFO пишет полный адрес запроса — у lk_api.php в нём токен ЛК (?getUser&token=…); только предупреждения
    logging.getLogger("httpx").setLevel(logging.WARNING)

    settings = Settings.from_env()
    sessionmaker = make_sessionmaker(make_engine(settings.database_url))
    mode: Mode = "http" if args.http else "stdio"
    server = create_server(build_services(settings, sessionmaker, mode=mode))

    # psycopg в async-режиме не работает с ProactorEventLoop (по умолчанию на Windows)
    options = {"loop_factory": asyncio.SelectorEventLoop} if sys.platform == "win32" else {}
    if args.http:
        run = functools.partial(server.run_streamable_http_async, host=args.host, port=args.port)
    else:
        run = server.run_stdio_async
    anyio.run(run, backend_options=options)


if __name__ == "__main__":
    main()
