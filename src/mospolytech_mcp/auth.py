# Авторизация в ЛК (ФЛК-001) и вызовы ЛК от имени пользователя (ТЭ-002) с журналом обращений (ФХД-004).
#
# Пароль используется один раз — при входе — и нигде не сохраняется. В БД лежат токены ЛК (зашифрованные
# MCP_SECRET_KEY) и хэши персональных ключей доступа к самому серверу (mpk_…).

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TypeVar

import httpx
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from .crypto import TokenCipher, hash_api_key, new_api_key
from .db import ApiKey, LKAccessLog, User, UserSession
from .lk_api import (
    APIError,
    InvalidCredentialsError,
    LKClient,
    LKError,
    NotAuthenticatedError,
    PasswordExpiredError,
    Tokens,
)

T = TypeVar("T")
LKFactory = Callable[[], LKClient]


class AuthError(Exception):
    """Вход не удался; текст — для пользователя."""


class NoSessionError(Exception):
    def __init__(self) -> None:
        super().__init__("нет активной сессии личного кабинета — войдите через lk_login")


class SessionExpiredError(Exception):
    def __init__(self) -> None:
        super().__init__("сессия личного кабинета истекла — войдите заново через lk_login")


class LKUnavailableError(Exception):
    """ЛК не ответил или ответил ошибкой (не связанной с авторизацией)."""


@dataclass
class LoginResult:
    user_id: int
    login: str
    full_name: str
    group: str | None
    api_key: str


def _short(exc: BaseException) -> str:
    text = str(exc) or type(exc).__name__
    return text if len(text) <= 300 else text[:300] + "…"


def _is_auth_failure(exc: BaseException) -> bool:
    """ЛК не принял токен. lk_api.php на протухший токен отвечает 400 с пустым телом (проверено 2026-10-07)."""
    if isinstance(exc, NotAuthenticatedError):
        return True
    if not isinstance(exc, APIError):
        return False
    if exc.status_code in (401, 403):
        return True
    return exc.op == "lk_api" and exc.status_code == 400 and not exc.body.strip()


class AccessLog:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def write(
        self,
        *,
        action: str,
        status: str,
        started: float,
        user_id: int | None = None,
        login: str | None = None,
        error: str | None = None,
    ) -> None:
        entry = LKAccessLog(
            user_id=user_id,
            login=login,
            action=action[:50],  # «messages:<id диалога>» — id в ЛК бывают длинными
            status=status,
            error=error,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        async with self._sessionmaker() as session:
            session.add(entry)
            await session.commit()


class AuthService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker,
        cipher: TokenCipher,
        lk_factory: LKFactory,
        access_log: AccessLog,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._cipher = cipher
        self._lk_factory = lk_factory
        self._log = access_log

    async def login(self, login: str, password: str, *, issue_key: bool = True, action: str = "login") -> LoginResult:
        """issue_key=False — только обновить сессию ЛК (автоперевход), ключи пользователя не трогать."""
        login = login.strip()
        if not login or not password:
            raise AuthError("нужны логин и пароль от личного кабинета")
        if not self._cipher.available:
            raise AuthError("сервер не настроен для входа: не задан MCP_SECRET_KEY")

        started = time.monotonic()
        client = self._lk_factory()
        try:
            tokens = await client.login(login, password)
            try:
                profile = await client.get_user()
            except (LKError, httpx.HTTPError):
                profile = None
        except InvalidCredentialsError as exc:
            await self._log.write(action=action, status="denied", started=started, login=login, error=str(exc))
            raise AuthError("неверный логин или пароль") from exc
        except PasswordExpiredError as exc:
            await self._log.write(action=action, status="denied", started=started, login=login, error=str(exc))
            raise AuthError("истёк срок действия пароля — смените его на e.mospolytech.ru и войдите снова") from exc
        except (LKError, httpx.HTTPError) as exc:
            await self._log.write(action=action, status="error", started=started, login=login, error=_short(exc))
            raise AuthError(f"личный кабинет недоступен: {_short(exc)}") from exc
        finally:
            await client.aclose()

        full_name = login
        group = None
        if profile is not None:
            full_name = " ".join(p for p in (profile.surname, profile.name, profile.patronymic) if p) or login
            group = profile.group or None
        guid = tokens.guid or (str(profile.id) if profile is not None and profile.id else login)

        now = datetime.now(UTC)
        api_key = new_api_key() if issue_key else ""
        async with self._sessionmaker() as session:
            user = await session.scalar(select(User).where(or_(User.guid == guid, User.login == login)))
            if user is None:
                user = User(guid=guid, login=login, full_name=full_name, group_name=group, last_login_at=now)
                session.add(user)
                await session.flush()
            else:
                user.guid, user.login, user.full_name, user.last_login_at = guid, login, full_name, now
                user.group_name = group or user.group_name
            await session.merge(
                UserSession(
                    user_id=user.id,
                    token_enc=self._cipher.encrypt(tokens.token),
                    jwt_enc=self._cipher.encrypt(tokens.jwt),
                    jwt_refresh_enc=self._cipher.encrypt(tokens.jwt_refresh),
                    refreshed_at=now,
                    updated_at=now,
                )
            )
            if issue_key:
                session.add(ApiKey(user_id=user.id, key_hash=hash_api_key(api_key), prefix=api_key[:12]))
            await session.commit()
            result = LoginResult(user.id, login, full_name, user.group_name, api_key)

        await self._log.write(action=action, status="ok", started=started, user_id=result.user_id)
        return result

    async def user_by_key(self, key: str) -> int | None:
        stmt = (
            update(ApiKey)
            .where(ApiKey.key_hash == hash_api_key(key), ApiKey.revoked_at.is_(None))
            .values(last_used_at=datetime.now(UTC))
            .returning(ApiKey.user_id)
        )
        async with self._sessionmaker() as session:
            user_id = await session.scalar(stmt)
            await session.commit()
        return user_id

    async def get_user(self, user_id: int) -> User | None:
        async with self._sessionmaker() as session:
            return await session.get(User, user_id)

    async def logout(self, user_id: int) -> int:
        """Выход везде: отзывает все ключи пользователя и удаляет токены ЛК. Возвращает число ключей."""
        now = datetime.now(UTC)
        async with self._sessionmaker() as session:
            revoked = await session.execute(
                update(ApiKey)
                .where(ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
            await session.commit()
        await self._log.write(action="logout", status="ok", started=time.monotonic(), user_id=user_id)
        return revoked.rowcount or 0


class LKGateway:
    """Любое обращение к ЛК от имени пользователя: его токены, обновление JWT, запись в журнал."""

    def __init__(
        self,
        sessionmaker: async_sessionmaker,
        cipher: TokenCipher,
        lk_factory: LKFactory,
        access_log: AccessLog,
        *,
        refresh_interval: timedelta = timedelta(minutes=30),
        auth: AuthService | None = None,
        relogin_credentials: dict[str, str] | None = None,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._cipher = cipher
        self._lk_factory = lk_factory
        self._log = access_log
        self._refresh_interval = refresh_interval
        self._auth = auth
        # логин → пароль: для этих учёток сервер сам входит заново, когда ЛК отверг сессию (LK_AUTO_RELOGIN)
        self._relogin = relogin_credentials or {}
        self._relogin_locks: dict[int, asyncio.Lock] = {}

    async def call(self, user_id: int, action: str, fn: Callable[[LKClient], Awaitable[T]]) -> T:
        try:
            return await self._call_once(user_id, action, fn)
        except (NoSessionError, SessionExpiredError):
            if not await self._try_relogin(user_id):
                raise
        return await self._call_once(user_id, action, fn)

    async def _try_relogin(self, user_id: int) -> bool:
        """Автоперевход по сохранённым на сервере логину и паролю — только для учёток из настроек."""
        if not self._relogin or self._auth is None:
            return False
        lock = self._relogin_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            async with self._sessionmaker() as session:
                if await session.get(UserSession, user_id) is not None:
                    return True  # пока ждали блокировку, сессию уже обновил параллельный вызов
                user = await session.get(User, user_id)
            password = self._relogin.get(user.login) if user is not None else None
            if password is None:
                return False
            try:
                await self._auth.login(user.login, password, issue_key=False, action="relogin")
            except AuthError:
                return False
            return True

    async def _call_once(self, user_id: int, action: str, fn: Callable[[LKClient], Awaitable[T]]) -> T:
        async with self._sessionmaker() as session:
            stored = await session.get(UserSession, user_id)
        if stored is None:
            raise NoSessionError()

        client = self._lk_factory()
        client.tokens = Tokens(
            token=self._cipher.decrypt(stored.token_enc),
            jwt=self._cipher.decrypt(stored.jwt_enc),
            jwt_refresh=self._cipher.decrypt(stored.jwt_refresh_enc),
        )
        before = (client.tokens.jwt, client.tokens.jwt_refresh)
        refreshed = False
        try:
            if client.tokens.jwt_refresh and datetime.now(UTC) - stored.refreshed_at >= self._refresh_interval:
                await self._refresh(client, user_id)
                # отметка refreshed_at сдвигается и при неудаче — следующая попытка через refresh_interval
                refreshed = True

            started = time.monotonic()
            try:
                result = await fn(client)
            except (LKError, httpx.HTTPError) as exc:
                expired = _is_auth_failure(exc) and await self._token_rejected(client)
                await self._log.write(
                    action=action, status="expired" if expired else "error",
                    started=started, user_id=user_id, error=_short(exc),
                )
                if expired:
                    await self._drop_session(user_id)
                    raise SessionExpiredError() from exc
                raise LKUnavailableError(_short(exc)) from exc
            await self._log.write(action=action, status="ok", started=started, user_id=user_id)

            if refreshed or (client.tokens.jwt, client.tokens.jwt_refresh) != before:
                await self._save_tokens(user_id, client.tokens)
            return result
        finally:
            await client.aclose()

    async def _token_rejected(self, client: LKClient) -> bool:
        """ЛК отвечает 400 и на протухший токен, и на неверный запрос: токен жив, если жив getUser."""
        try:
            await client.lk_get("getUser")
        except (LKError, httpx.HTTPError) as exc:
            return _is_auth_failure(exc)
        return False

    async def _refresh(self, client: LKClient, user_id: int) -> None:
        started = time.monotonic()
        try:
            await client.refresh_token()
        except (LKError, httpx.HTTPError) as exc:
            # легаси-токен для lk_api.php может быть ещё жив — не мешаем основному вызову
            await self._log.write(action="token_refresh", status="error", started=started, user_id=user_id, error=_short(exc))
            return
        await self._log.write(action="token_refresh", status="ok", started=started, user_id=user_id)

    async def _save_tokens(self, user_id: int, tokens: Tokens) -> None:
        now = datetime.now(UTC)
        async with self._sessionmaker() as session:
            await session.execute(
                update(UserSession)
                .where(UserSession.user_id == user_id)
                .values(
                    jwt_enc=self._cipher.encrypt(tokens.jwt),
                    jwt_refresh_enc=self._cipher.encrypt(tokens.jwt_refresh),
                    refreshed_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    async def _drop_session(self, user_id: int) -> None:
        async with self._sessionmaker() as session:
            await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
            await session.commit()

