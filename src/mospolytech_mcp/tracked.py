# Отслеживаемые пользователем группы: хранятся в tracked_groups, привязаны к пользователю по user_id.

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from .db import TrackedGroup


class UnknownGroupError(ValueError):
    pass


class TrackedGroupsStore:
    def __init__(
        self,
        sessionmaker: async_sessionmaker,
        known_groups: Callable[[], Awaitable[list[str]]],
    ) -> None:
        self._sessionmaker = sessionmaker
        self._known_groups = known_groups

    async def add(self, user_id: int, user_login: str, group_name: str) -> bool:
        """user_login пишется для совместимости со старой привязкой по логину (столбец ещё NOT NULL)."""
        group_name = group_name.strip()
        if group_name not in await self._known_groups():
            raise UnknownGroupError(f"группы {group_name!r} нет в списке групп университета")

        stmt = (
            insert(TrackedGroup)
            .values(user_id=user_id, user_login=user_login, group_name=group_name)
            .on_conflict_do_nothing(index_elements=["user_id", "group_name"])
            .returning(TrackedGroup.id)
        )
        async with self._sessionmaker() as session:
            new_id = await session.scalar(stmt)
            await session.commit()
        return new_id is not None

    async def list(self, user_id: int) -> list[str]:
        stmt = (
            select(TrackedGroup.group_name)
            .where(TrackedGroup.user_id == user_id)
            .order_by(TrackedGroup.created_at, TrackedGroup.id)
        )
        async with self._sessionmaker() as session:
            return list(await session.scalars(stmt))

    async def remove(self, user_id: int, group_name: str) -> bool:
        stmt = (
            delete(TrackedGroup)
            .where(
                TrackedGroup.user_id == user_id,
                TrackedGroup.group_name == group_name.strip(),
            )
            .returning(TrackedGroup.id)
        )
        async with self._sessionmaker() as session:
            removed_id = await session.scalar(stmt)
            await session.commit()
        return removed_id is not None
