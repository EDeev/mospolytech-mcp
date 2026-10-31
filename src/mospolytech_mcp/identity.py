# Кто вызывает инструмент: персональный ключ (Authorization: Bearer mpk_…), вход в рамках подключения
# (stdio или сессия HTTP старых версий протокола) или вход по MPU_API_KEY / MPU_LOGIN+MPU_PASSWORD для stdio.

from __future__ import annotations

import weakref
from typing import Any, Literal

from mcp.server.mcpserver import Context

from .auth import AuthError, AuthService
from .crypto import API_KEY_PREFIX

Mode = Literal["stdio", "http"]


class NotLoggedInError(Exception):
    def __init__(self, reason: str | None = None) -> None:
        text = (
            "нужна авторизация в личном кабинете: вызовите lk_login(login, password) "
            "или передайте персональный ключ в заголовке Authorization: Bearer mpk_…"
        )
        super().__init__(f"{text} ({reason})" if reason else text)


class InvalidKeyError(Exception):
    def __init__(self) -> None:
        super().__init__("персональный ключ недействителен или отозван — войдите заново через lk_login")


def bearer_key(headers: Any) -> str | None:
    if not headers:
        return None
    value = headers.get("authorization") or headers.get("Authorization") or ""
    scheme, _, token = value.partition(" ")
    token = token.strip()
    if scheme.lower() == "bearer" and token.startswith(API_KEY_PREFIX):
        return token
    return None


class Identity:
    def __init__(
        self,
        auth: AuthService,
        *,
        mode: Mode,
        api_key: str | None = None,
        autologin: tuple[str, str] | None = None,
    ) -> None:
        self._auth = auth
        self._mode = mode
        self._api_key = api_key if mode == "stdio" else None
        self._autologin = autologin if mode == "stdio" else None
        self._autologin_error: str | None = None
        self._process_user: int | None = None
        self._by_session: weakref.WeakKeyDictionary[Any, int] = weakref.WeakKeyDictionary()

    @property
    def mode(self) -> Mode:
        return self._mode

    def _headers(self, ctx: Context) -> Any:
        try:
            return ctx.headers
        except (AssertionError, AttributeError, LookupError):
            return None

    def _session(self, ctx: Context) -> Any:
        """Объект подключения: ServerSession создаётся на каждый запрос, а Connection живёт всю сессию."""
        try:
            session = ctx.session
        except (AssertionError, AttributeError, LookupError):
            return None
        return getattr(session, "connection", None) or getattr(session, "_connection", None) or session

    async def resolve(self, ctx: Context) -> int | None:
        key = bearer_key(self._headers(ctx))
        if key:
            user_id = await self._auth.user_by_key(key)
            if user_id is None:
                raise InvalidKeyError()
            return user_id

        if self._mode == "stdio":
            if self._process_user is not None:
                return self._process_user
            return await self._stdio_login()

        session = self._session(ctx)
        if session is not None:
            return self._by_session.get(session)
        return None

    async def require(self, ctx: Context) -> int:
        user_id = await self.resolve(ctx)
        if user_id is None:
            raise NotLoggedInError(self._autologin_error)
        return user_id

    def bind(self, ctx: Context, user_id: int) -> None:
        if self._mode == "stdio":
            self._process_user = user_id
            self._autologin_error = None
            return
        session = self._session(ctx)
        if session is not None:
            self._by_session[session] = user_id

    def forget(self, user_id: int) -> None:
        if self._process_user == user_id:
            self._process_user = None
        for session, bound in list(self._by_session.items()):
            if bound == user_id:
                del self._by_session[session]

    async def _stdio_login(self) -> int | None:
        if self._api_key:
            user_id = await self._auth.user_by_key(self._api_key)
            if user_id is not None:
                self._process_user = user_id
                return user_id
            self._autologin_error = "ключ из MPU_API_KEY недействителен"
        if self._autologin and self._autologin_error is None:
            login, password = self._autologin
            try:
                result = await self._auth.login(login, password)
            except AuthError as exc:
                # одна попытка на процесс — не перебираем пароль на каждом вызове
                self._autologin_error = f"вход по MPU_LOGIN не удался: {exc}"
                return None
            self._process_user = result.user_id
            return result.user_id
        return None
