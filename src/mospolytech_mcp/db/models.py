# Модели БД (SQLAlchemy ORM).

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GroupsCache(Base):
    __tablename__ = "groups_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    groups: Mapped[list[str]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class TrackedGroup(Base):
    __tablename__ = "tracked_groups"
    __table_args__ = (UniqueConstraint("user_login", "group_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_login: Mapped[str] = mapped_column(String(100), index=True)
    group_name: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
