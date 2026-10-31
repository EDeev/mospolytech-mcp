# Вызов инструментов сервера через настоящий MCP-клиент (в том же процессе).

from __future__ import annotations

from typing import Any

from mcp import Client


class ToolFailed(Exception):
    pass


async def call(client: Client, name: str, **arguments: Any) -> Any:
    result = await client.call_tool(name, arguments)
    if result.is_error:
        raise ToolFailed(" ".join(getattr(c, "text", "") for c in result.content))
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {"result"}:
        return data["result"]
    return data
