# UniversityAPI: единая точка входа, объединяющая клиентов open_api и lk_api.

from __future__ import annotations

import httpx

from .lk_api import LKClient
from .open_api import OpenDataClient

__all__ = ["UniversityAPI"]


class UniversityAPI:
    def __init__(self, *, lk_http_client: httpx.AsyncClient | None = None) -> None:
        self.open = OpenDataClient()
        self.lk = LKClient(http_client=lk_http_client)

    async def __aenter__(self) -> "UniversityAPI":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.lk.aclose()
