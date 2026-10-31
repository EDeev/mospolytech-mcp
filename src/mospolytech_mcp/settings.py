# Настройки сервера из окружения (.env): БД, ключ шифрования, сроки кэша, вход по умолчанию для stdio.

from __future__ import annotations

import os
from dataclasses import dataclass, field
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
    schedule_ttl: timedelta = timedelta(hours=6)
    # индекс преподавателей пересобирается не чаще, чем раз в teacher_index_ttl
    teacher_index: bool = True
    teacher_index_ttl: timedelta = timedelta(hours=24)
    # сроки свежести персональных данных из ЛК, по видам
    personal_ttl: dict[str, timedelta] = field(
        default_factory=lambda: {
            "profile": timedelta(hours=24),  # меняется редко; группа для my_schedule — из student_profiles
            "schedule": timedelta(hours=1),
            "performance": timedelta(hours=1),
            "notifications": timedelta(minutes=5),
            "payments": timedelta(hours=1),
            "requests": timedelta(minutes=30),
            "dialogs": timedelta(minutes=1),
            "messages": timedelta(minutes=1),
            "group_chat": timedelta(hours=24),
        }
    )
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
            schedule_ttl=_minutes("SCHEDULE_TTL_MINUTES", 360),
            teacher_index=_flag("TEACHER_INDEX", True),
            teacher_index_ttl=_minutes("TEACHER_INDEX_TTL_MINUTES", 24 * 60),
            personal_ttl=defaults.personal_ttl,
            jwt_refresh_interval=defaults.jwt_refresh_interval,
            public_url=(os.environ.get("MCP_PUBLIC_URL") or "").rstrip("/") or None,
        )
