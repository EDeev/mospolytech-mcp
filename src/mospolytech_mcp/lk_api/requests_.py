# Поданные заявки/обращения пользователя (ФЛК-005).

from __future__ import annotations

from .models import AppRequest


class RequestsMixin:
    async def get_app_requests(self) -> list[AppRequest]:
        raw = await self.lk_get("getAppRequests")  # type: ignore[attr-defined]
        return [AppRequest.from_dict(r) for r in raw or []]
