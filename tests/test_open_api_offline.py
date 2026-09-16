# Офлайн-тесты обёртки над открытым API (open_api).

from __future__ import annotations
import json
import pytest

from mospolytech_mcp.open_api import OpenDataClient
from mospolytech_mcp.open_api._vendor import api as vendor_api_module


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


def test_client_initializes_with_bundled_hash_salt():
    OpenDataClient()


async def test_get_groups_parses_response(monkeypatch):
    def fake_get(url, headers=None):
        assert url == vendor_api_module.API._API__URLS["groups"]
        body = json.dumps({"groups": ["201-722", "201-721"]}).encode("utf-8")
        return _FakeResponse(200, body)

    monkeypatch.setattr(vendor_api_module.requests, "get", fake_get)

    client = OpenDataClient()
    groups = await client.get_groups()
    assert groups == ["201-721", "201-722"]


async def test_get_schedule_parses_response(monkeypatch):
    grid = {
        "14.09.2026": {
            "0": [
                {
                    "sbj": "Матанализ",
                    "type": "лекция",
                    "teacher": "Петров П. П.",
                    "location": "ауд. 101",
                    "shortRooms": ["101"],
                    "e_link": None,
                    "auditories": [{"title": "ауд. 101"}],
                }
            ]
        }
    }
    payload = {
        "group": {"evening": False, "dateFrom": "2026-09-14", "dateTo": "2026-09-14"},
        "isSession": False,
        "grid": grid,
    }

    def fake_get(url, headers=None):
        return _FakeResponse(200, json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(vendor_api_module.requests, "get", fake_get)

    client = OpenDataClient()
    schedule = await client.get_schedule("201-721", is_session=False)
    assert schedule["group"] == "201-721"
    assert schedule["type"] == "morning"
    assert schedule["dates"] == ["14.09.2026", "14.09.2026"]


async def test_get_groups_raises_on_bad_status(monkeypatch):
    def fake_get(url, headers=None):
        return _FakeResponse(500, b"")

    monkeypatch.setattr(vendor_api_module.requests, "get", fake_get)

    client = OpenDataClient()
    with pytest.raises(Exception):
        await client.get_groups()
