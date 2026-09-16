# Общий declarative base для всех моделей — одна metadata для Alembic.

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
