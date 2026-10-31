# Настройки сервера из окружения (.env): БД, ключ шифрования, срок кэша групп, вход по умолчанию для stdio.

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta


def _minutes(name: str, default: int) -> timedelta:
    return timedelta(minutes=int(os.environ.get(name) or default))


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str | None = None
    # ключ Fernet для шифрования токенов ЛК в БД (MCP_SECRET_KEY)
    secret_key: str | None = None
    # логин/пароль ЛК для локального режима stdio — вход без вызова lk_login
    lk_login: str | None = None
    lk_password: str | None = None
    # персональный ключ mpk_… для режима stdio — вход без пароля в .env
    api_key: str | None = None
    # автоперевход в ЛК по MPU_LOGIN/MPU_PASSWORD, когда ЛК отверг сессию (личный сервер владельца, например для Davi)
    auto_relogin: bool = False
    groups_ttl: timedelta = timedelta(minutes=15)
    # как часто обновлять JWT по refresh-токену (ФЛК-001)
    jwt_refresh_interval: timedelta = timedelta(minutes=30)
    public_url: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            database_url=os.environ.get("DATABASE_URL") or None,
            secret_key=os.environ.get("MCP_SECRET_KEY") or None,
            lk_login=os.environ.get("MPU_LOGIN") or None,
            lk_password=os.environ.get("MPU_PASSWORD") or None,
            api_key=os.environ.get("MPU_API_KEY") or None,
            auto_relogin=_flag("LK_AUTO_RELOGIN", False),
            groups_ttl=_minutes("GROUPS_TTL_MINUTES", 15),
            jwt_refresh_interval=defaults.jwt_refresh_interval,
            public_url=(os.environ.get("MCP_PUBLIC_URL") or "").rstrip("/") or None,
        )
