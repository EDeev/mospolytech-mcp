# Собранный клиент личного кабинета — публичная точка входа пакета.

from __future__ import annotations

from .base import DEFAULT_API_BASE_URL, DEFAULT_LK_BASE_URL, LKClientBase
from .messages import MessagesMixin
from .notifications import NotificationsMixin
from .payments import PaymentsMixin
from .performance import PerformanceMixin
from .requests_ import RequestsMixin
from .schedule import ScheduleMixin
from .user import UserMixin

__all__ = ["LKClient", "DEFAULT_LK_BASE_URL", "DEFAULT_API_BASE_URL"]


class LKClient(
    LKClientBase,
    UserMixin,
    ScheduleMixin,
    PerformanceMixin,
    PaymentsMixin,
    NotificationsMixin,
    RequestsMixin,
    MessagesMixin,
):
    pass
