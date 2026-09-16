# Профиль пользователя личного кабинета.

from __future__ import annotations

from .errors import APIError
from .models import User


class UserMixin:
    async def get_user(self) -> User:
        raw = await self.lk_get("getUser")  # type: ignore[attr-defined]
        if not isinstance(raw, dict) or "user" not in raw:
            raise APIError("getUser", 200, str(raw))
        user_data = raw["user"]
        if not isinstance(user_data, dict):
            raise APIError("getUser", 200, str(raw))
        return User.from_dict(user_data)
