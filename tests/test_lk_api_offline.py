# Офлайн-тесты клиента личного кабинета (через httpx.MockTransport).

from __future__ import annotations

import json

import httpx
import pytest

from mospolytech_mcp.lk_api import (
    APIError,
    InvalidCredentialsError,
    LKClient,
    NotAuthenticatedError,
    NoRefreshTokenError,
    PasswordExpiredError,
)


def make_client(handler) -> LKClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return LKClient(http_client=http_client)


async def test_login_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old/lk_api.php" and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "token": "legacy-token",
                    "jwt": "jwt-access",
                    "jwt_refresh": "jwt-refresh",
                    "guid": "guid-123",
                },
            )

        return httpx.Response(200, text="")

    client = make_client(handler)
    async with client:
        tokens = await client.login("user@example.com", "secret")
        assert tokens.token == "legacy-token"
        assert tokens.jwt == "jwt-access"
        assert tokens.jwt_refresh == "jwt-refresh"
        assert tokens.guid == "guid-123"
        assert client.is_authenticated is True


async def test_login_invalid_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="")

    client = make_client(handler)
    async with client:
        with pytest.raises(InvalidCredentialsError):
            await client.login("user@example.com", "wrong")


async def test_login_password_expired():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"token": "", "AD_pwd_expired": True, "AD_domain": "staff"},
        )

    client = make_client(handler)
    async with client:
        with pytest.raises(PasswordExpiredError) as exc_info:
            await client.login("staff.member", "old-pass")
        assert exc_info.value.ad_domain == "staff"


async def test_lk_get_requires_authentication():
    client = make_client(lambda request: httpx.Response(200))
    async with client:
        with pytest.raises(NotAuthenticatedError):
            await client.get_user()


async def test_get_user_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["getUser"] == ""
        assert request.url.params["token"] == "legacy-token"
        return httpx.Response(
            200,
            json={
                "user": {
                    "id": 42,
                    "name": "Иван",
                    "surname": "Иванов",
                    "course": 3,  
                    "is_token_valid": True,
                    "hasAlerts": False,
                }
            },
        )

    client = make_client(handler)
    client.tokens.token = "legacy-token"
    async with client:
        user = await client.get_user()
        assert user.id == 42
        assert user.name == "Иван"
        assert user.course == "3"
        assert user.is_token_valid is True


async def test_refresh_token_updates_jwt():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/token/reissue"
        body = json.loads(request.content)
        assert body["refresh_token"] == "old-refresh"
        return httpx.Response(
            200, json={"access_token": "new-jwt", "refresh_token": "new-refresh"}
        )

    client = make_client(handler)
    client.tokens.jwt_refresh = "old-refresh"
    async with client:
        await client.refresh_token()
        assert client.tokens.jwt == "new-jwt"
        assert client.tokens.jwt_refresh == "new-refresh"


async def test_refresh_token_without_refresh_token_raises():
    client = make_client(lambda request: httpx.Response(200))
    async with client:
        with pytest.raises(NoRefreshTokenError):
            await client.refresh_token()


async def test_get_my_schedule_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "2026-09-14": {
                    "lessons": [
                        {
                            "name": "Матанализ",
                            "timeInterval": "09:00-10:30",
                            "place": "ауд. 101",
                            "rooms": ["101"],
                            "teachers": ["Петров П. П."],
                            "dateInterval": "",
                            "link": "",
                            "teachersFull": [{"id": 1, "name": "Петров П. П."}],
                        }
                    ]
                }
            },
        )

    client = make_client(handler)
    client.tokens.token = "legacy-token"
    async with client:
        schedule = await client.get_my_schedule()
        day = schedule["2026-09-14"]
        assert len(day.lessons) == 1
        assert day.lessons[0].name == "Матанализ"
        assert day.lessons[0].teachers_full[0].name == "Петров П. П."


async def test_lk_api_error_on_invalid_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="не json")

    client = make_client(handler)
    client.tokens.token = "legacy-token"
    async with client:
        with pytest.raises(APIError):
            await client.get_notifications()


async def test_lk_api_error_on_bad_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    client = make_client(handler)
    client.tokens.token = "legacy-token"
    async with client:
        with pytest.raises(APIError) as exc_info:
            await client.get_notifications()
        assert exc_info.value.status_code == 500
