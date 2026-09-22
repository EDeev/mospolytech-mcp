# MCP-сервер mospolytech-mcp: инструменты поверх UniversityAPI (транспорт stdio).

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ._dotenv import load_dotenv
from .api import UniversityAPI
from .cache import GroupsCacheStore
from .db import make_engine, make_sessionmaker

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

mcp = MCPServer(name="mospolytech-mcp", version="0.1.0")

_uni = UniversityAPI()
_engine = make_engine()
_groups_cache = GroupsCacheStore(_uni.open, make_sessionmaker(_engine))


@mcp.tool()
async def list_groups() -> list[str]:
    """Список всех учебных групп Московского Политеха."""
    return await _groups_cache.get_groups()


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
