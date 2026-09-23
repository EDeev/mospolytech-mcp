# MCP-сервер mospolytech-mcp: инструменты поверх UniversityAPI (транспорт stdio).

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from ._dotenv import load_dotenv
from .api import UniversityAPI
from .cache import GroupsCacheStore
from .db import make_engine, make_sessionmaker
from .tracked import TrackedGroupsStore, UnknownGroupError

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

mcp = MCPServer(name="mospolytech-mcp", version="0.1.0")

_uni = UniversityAPI()
_engine = make_engine()
_sessionmaker = make_sessionmaker(_engine)
_groups_cache = GroupsCacheStore(_uni.open, _sessionmaker)
_tracked = TrackedGroupsStore(_sessionmaker, _groups_cache.get_groups)


@mcp.tool()
async def list_groups() -> list[str]:
    """Список всех учебных групп Московского Политеха."""
    return await _groups_cache.get_groups()


@mcp.tool()
async def add_tracked_group(user: str, group: str) -> str:
    """Добавить группу в отслеживаемые для пользователя. group — номер вида 241-327."""
    try:
        added = await _tracked.add(user, group)
    except UnknownGroupError as exc:
        raise ToolError(str(exc)) from exc
    if added:
        return f"группа {group} добавлена в отслеживаемые для {user}"
    return f"группа {group} уже отслеживается для {user}"


@mcp.tool()
async def list_tracked_groups(user: str) -> list[str]:
    """Группы, которые отслеживает пользователь, в порядке добавления."""
    return await _tracked.list(user)


@mcp.tool()
async def remove_tracked_group(user: str, group: str) -> str:
    """Убрать группу из отслеживаемых для пользователя."""
    if await _tracked.remove(user, group):
        return f"группа {group} больше не отслеживается для {user}"
    return f"группа {group} не была в отслеживаемых для {user}"


def main() -> None:
    parser = argparse.ArgumentParser(prog="mospolytech-mcp")
    parser.add_argument("--http", action="store_true", help="HTTP вместо stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
