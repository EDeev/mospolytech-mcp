# HTTP-страницы рядом с MCP: /health и вход через браузер /login.

from __future__ import annotations

import httpx
from sqlalchemy import func, select

from mospolytech_mcp.db import ApiKey
from mospolytech_mcp.server import create_server

from .fakes import FakeLK

FORM = {"content-type": "application/x-www-form-urlencoded"}


def web_client(services) -> httpx.AsyncClient:
    app = create_server(services).streamable_http_app()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://mcp.test")


async def test_health(services):
    async with web_client(services) as http:
        response = await http.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" and response.json()["teacher_index"] is None


async def test_login_page_issues_key(services, sessionmaker):
    async with web_client(services) as http:
        page = await http.get("/login")
        assert page.status_code == 200 and "<form" in page.text

        wrong = await http.post("/login", content=f"login={FakeLK.LOGIN}&password=nope", headers=FORM)
        assert wrong.status_code == 401 and "неверный логин или пароль" in wrong.text

        ok = await http.post("/login", content=f"login={FakeLK.LOGIN}&password={FakeLK.PASSWORD}", headers=FORM)
        assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
        assert "Bearer mpk_" in ok.text and "http://mcp.test/mcp" in ok.text

    async with sessionmaker() as session:
        assert await session.scalar(select(func.count()).select_from(ApiKey)) == 1


async def test_login_page_rate_limit(services):
    async with web_client(services) as http:
        codes = [
            (await http.post("/login", content="login=x&password=y", headers=FORM)).status_code for _ in range(6)
        ]
    assert codes == [401] * 5 + [429]
