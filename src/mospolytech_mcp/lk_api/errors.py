# Исключения клиента личного кабинета.

from __future__ import annotations


class LKError(Exception):
    pass


class InvalidCredentialsError(LKError):
    def __init__(self) -> None:
        super().__init__("неверный логин или пароль")


class NotAuthenticatedError(LKError):
    def __init__(self) -> None:
        super().__init__("клиент не авторизован — сначала вызовите login()")


class NoRefreshTokenError(LKError):
    def __init__(self) -> None:
        super().__init__("refresh-токен отсутствует")


class PasswordExpiredError(LKError):
    def __init__(self, login: str, ad_domain: str) -> None:
        self.login = login
        self.ad_domain = ad_domain
        super().__init__(
            f"истёк пароль доменной учётной записи {login!r} (домен {ad_domain!r})"
        )


class APIError(LKError):
    def __init__(self, op: str, status_code: int, body: str) -> None:
        self.op = op
        self.status_code = status_code
        self.body = body
        shown = body if len(body) <= 500 else body[:500] + "…"
        super().__init__(f"{op}: неожиданный статус {status_code}: {shown}")
