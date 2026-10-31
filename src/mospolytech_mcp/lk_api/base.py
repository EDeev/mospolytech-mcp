# Ядро клиента ЛК: HTTP-транспорт, токены, логин/логаут, обновление JWT.

from __future__ import annotations

import ssl
from functools import cache
from typing import Any

import certifi
import httpx

from ._certs import GLOBALSIGN_GCC_R46_DV_TLS_CA_2025
from .errors import (
    APIError,
    InvalidCredentialsError,
    NoRefreshTokenError,
    NotAuthenticatedError,
    PasswordExpiredError,
)
from .models import Tokens

# Старый PHP API ЛК с 2026-10-30 — отдельный домен; e.mospolytech.ru/old/lk_api.php теперь отдаёт страницу
# фронтенда, а на POST отвечает 405.
DEFAULT_LK_BASE_URL = "https://old-e.mospolytech.ru"
DEFAULT_API_BASE_URL = "https://api.mospolytech.ru"
# Соединение — 5 с: недоступный хост (api.mospolytech.ru с 2026-10-09 не принимает соединения) не должен держать
# инструмент полминуты; ответ ЛК после соединения — по-прежнему до timeout.
CONNECT_TIMEOUT = 5.0


@cache
def lk_ssl_context() -> ssl.SSLContext:
    """certifi + промежуточный GlobalSign, которого сервер ЛК не присылает (см. _certs.py)."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(cadata=GLOBALSIGN_GCC_R46_DV_TLS_CA_2025)
    return ctx


class LKClientBase:
    def __init__(
        self,
        *,
        lk_base_url: str = DEFAULT_LK_BASE_URL,
        api_base_url: str = DEFAULT_API_BASE_URL,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT), follow_redirects=True, verify=lk_ssl_context()
        )
        self._lk_base_url = lk_base_url.rstrip("/")
        self._api_base_url = api_base_url.rstrip("/")
        self.tokens = Tokens()

    async def __aenter__(self) -> "LKClientBase":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.tokens.token)

    async def login(self, login: str, password: str) -> Tokens:
        resp = await self._http.post(
            f"{self._lk_base_url}/lk_api.php",
            data={"ulogin": login, "upassword": password},
        )

        if resp.status_code == 400:
            raise InvalidCredentialsError()
        if resp.status_code != 200:
            raise APIError("login", resp.status_code, resp.text)

        try:
            data = resp.json()
        except ValueError as exc:
            raise APIError("login", resp.status_code, resp.text) from exc

        token = data.get("token") or ""

        if data.get("AD_pwd_expired") and not token:
            domain = data.get("AD_domain") or "staff"
            raise PasswordExpiredError(login=login, ad_domain=domain)
        if not token:
            raise APIError("login", resp.status_code, resp.text)

        tokens = Tokens(
            token=token,
            jwt=data.get("jwt") or "",
            jwt_refresh=data.get("jwt_refresh") or "",
            guid=data.get("guid") or "",
        )

        await self._establish_php_session(login, password)

        self.tokens = tokens
        return tokens

    async def _establish_php_session(self, login: str, password: str) -> None:
        try:
            await self._http.post(
                self._lk_base_url,
                files={
                    "ulogin": (None, login),
                    "upassword": (None, password),
                    "auth_action": (None, "userlogin"),
                },
            )
        except httpx.HTTPError:
            pass

    def logout(self) -> None:
        self.tokens = Tokens()

    async def refresh_token(self) -> None:
        refresh = self.tokens.jwt_refresh
        if not refresh:
            raise NoRefreshTokenError()

        resp = await self._http.post(
            f"{self._api_base_url}/auth/token/reissue",
            json={"refresh_token": refresh},
        )
        if resp.status_code != 200:
            raise APIError("token/reissue", resp.status_code, resp.text)

        try:
            data = resp.json()
        except ValueError as exc:
            raise APIError("token/reissue", resp.status_code, resp.text) from exc

        access_token = data.get("access_token") or ""
        if not access_token:
            raise APIError("token/reissue", resp.status_code, resp.text)

        self.tokens.jwt = access_token
        self.tokens.jwt_refresh = data.get("refresh_token") or self.tokens.jwt_refresh

    async def lk_get(self, query: str) -> Any:
        return await self._lk_request("GET", query)

    async def lk_post_form(
        self, query: str, form: dict[str, str] | None = None
    ) -> Any:
        return await self._lk_request("POST", query, data=form)

    async def lk_post_multipart(self, query: str, fields: dict[str, str]) -> Any:
        """POST multipart/form-data — так фронтенд ЛК отправляет сообщения."""
        return await self._lk_request("POST", query, files={k: (None, v) for k, v in fields.items()})

    async def _lk_request(
        self,
        method: str,
        query: str,
        data: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        if not self.tokens.token:
            raise NotAuthenticatedError()

        url = f"{self._lk_base_url}/lk_api.php?"
        if query:
            url += query + "&"
        url += "token=" + self.tokens.token

        resp = await self._http.request(method, url, data=data, files=files)
        if resp.status_code != 200:
            raise APIError("lk_api", resp.status_code, resp.text)

        raw = resp.text
        if not raw:
            return None
        try:
            return resp.json()
        except ValueError as exc:
            raise APIError("lk_api", resp.status_code, raw) from exc

    async def api_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
    ) -> httpx.Response:
        if not self.tokens.jwt:
            raise NotAuthenticatedError()

        url = f"{self._api_base_url}{path}"
        headers = {"Authorization": f"Bearer {self.tokens.jwt}"}
        resp = await self._http.request(method, url, json=json_body, headers=headers)
        if resp.status_code != 401:
            return resp

        await self.refresh_token()
        headers = {"Authorization": f"Bearer {self.tokens.jwt}"}
        return await self._http.request(method, url, json=json_body, headers=headers)
