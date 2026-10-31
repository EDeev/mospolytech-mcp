# Модели БД (SQLAlchemy ORM); схема — миграции в alembic/versions/.

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


# ── Открытые данные (ФОД, ФХД-003) ───────────────────────────────────────────


class GroupsCache(Base):
    __tablename__ = "groups_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    groups: Mapped[list[str]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ScheduleCache(Base):
    """Расписание группы (семестр или сессия) из открытого API, с TTL."""

    __tablename__ = "schedule_cache"

    group_name: Mapped[str] = mapped_column(String(50), primary_key=True)
    is_session: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TeacherLesson(Base):
    """Индекс занятий по преподавателям — собирается из расписаний всех групп."""

    __tablename__ = "teacher_lessons"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher: Mapped[str] = mapped_column(String(200), index=True)
    group_name: Mapped[str] = mapped_column(String(50), index=True)
    is_session: Mapped[bool] = mapped_column(Boolean)
    # семестр: день недели 1–7; сессия: конкретная дата
    weekday: Mapped[int | None] = mapped_column(SmallInteger)
    lesson_date: Mapped[date | None] = mapped_column(Date)
    pair: Mapped[int] = mapped_column(SmallInteger)
    subject: Mapped[str] = mapped_column(String(300))
    lesson_type: Mapped[str] = mapped_column(String(100))
    rooms: Mapped[list[str]] = mapped_column(JSONB)
    location: Mapped[str] = mapped_column(String(200))
    link: Mapped[str | None] = mapped_column(Text)
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)


class ServiceState(Base):
    """Служебные отметки сервера (например, когда пересобран индекс преподавателей)."""

    __tablename__ = "service_state"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# ── Пользователи и авторизация (ФЛК-001, ТЭ-002) ─────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    guid: Mapped[str] = mapped_column(String(64), unique=True)
    login: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(300))
    group_name: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class UserSession(Base):
    """Токены ЛК пользователя, зашифрованные (пароль не хранится никогда)."""

    __tablename__ = "user_sessions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    token_enc: Mapped[str] = mapped_column(Text)
    jwt_enc: Mapped[str] = mapped_column(Text)
    jwt_refresh_enc: Mapped[str] = mapped_column(Text)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApiKey(Base):
    """Персональный ключ доступа к серверу (Authorization: Bearer mpk_…); хранится только хэш."""

    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LKAccessLog(Base):
    """Журнал обращений к API личного кабинета (ФХД-004). Открытый API сюда не пишется."""

    __tablename__ = "lk_access_log"
    __table_args__ = (Index("ix_lk_access_log_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    # логин — только для попыток входа, когда пользователя ещё нет
    login: Mapped[str | None] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ── Отслеживаемые группы ─────────────────────────────────────────────────────


class TrackedGroup(Base):
    __tablename__ = "tracked_groups"
    __table_args__ = (UniqueConstraint("user_login", "group_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_login: Mapped[str] = mapped_column(String(100), index=True)
    group_name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
