# Async-обёртка над синхронной вендоренной mospolytech_api (asyncio.to_thread).

from __future__ import annotations

import asyncio
from pathlib import Path

from ._vendor.api import API
from ._vendor.schedule import Schedule

_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"
_DEFAULT_HASH_SALT_PATH = _VENDOR_DIR / "hash_salt.txt"

__all__ = ["OpenDataClient", "Schedule"]


class OpenDataClient:
    def __init__(self, *, hash_salt_path: str | Path = _DEFAULT_HASH_SALT_PATH) -> None:
        self._api = API(hash_salt_path=str(hash_salt_path))

    async def get_groups(self) -> list[str]:
        return await asyncio.to_thread(self._api.get_groups)

    async def get_schedule(self, group: str, *, is_session: bool = False) -> dict:
        return await asyncio.to_thread(self._api.get_schedule, group, is_session)

    async def get_students(self, groups: list[str] | None = None) -> dict:
        return await asyncio.to_thread(self._api.get_students, groups)

    async def get_semester(self) -> dict:
        return await asyncio.to_thread(self._api.get_semester)

    async def get_session(self) -> dict:
        return await asyncio.to_thread(self._api.get_session)
