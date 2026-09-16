# Модели БД (SQLAlchemy ORM).

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class GroupsCache(Base):
    __tablename__ = "groups_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    groups: Mapped[list[str]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
