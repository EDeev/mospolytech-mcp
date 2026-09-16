# Уведомления и объявления личного кабинета (ФЛК-004).

from __future__ import annotations

from .models import Alert, Notification


class NotificationsMixin:
    async def get_notifications(self) -> list[Notification]:
        raw = await self.lk_get("getNotifications")  # type: ignore[attr-defined]
        return [Notification.from_dict(n) for n in raw or []]

    async def get_alerts(self) -> list[Alert]:
        raw = await self.lk_get("getAlerts")  # type: ignore[attr-defined]
        return [Alert.from_dict(a) for a in raw or []]
