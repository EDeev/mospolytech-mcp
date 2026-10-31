# Нагрузочная проверка ТСФ-003 и ТП-001: N клиентов шлют запросы к серверу по HTTP с заданной частотой.
#
#   python scripts/load_test.py http://127.0.0.1:8000/mcp --rps 10 --seconds 30 --clients 10
#   python scripts/load_test.py ... --key mpk_aaa --key mpk_bbb   # плюс инструменты ЛК от разных пользователей
#
# Без ключей вызываются только открытые инструменты (расписания групп из кэша), с ключами — ещё my_profile.

from __future__ import annotations

import argparse
import asyncio
import random
import statistics
import sys
import time

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

GROUPS = ["241-321", "241-322", "241-323", "241-324", "241-325", "241-326", "241-327", "241-328"]


async def worker(url: str, key: str | None, interval: float, until: float, results: list, errors: list) -> None:
    headers = {"Authorization": f"Bearer {key}"} if key else None
    http = httpx2.AsyncClient(headers=headers, timeout=30, trust_env=False)
    async with Client(streamable_http_client(url, http_client=http)) as client:
        await asyncio.sleep(random.random() * interval)
        while time.monotonic() < until:
            tool, args = ("my_profile", {}) if key and random.random() < 0.3 else (
                "group_schedule", {"group": random.choice(GROUPS), "date": "завтра"}
            )
            started = time.monotonic()
            try:
                result = await client.call_tool(tool, args)
                if result.is_error:
                    errors.append(result.content[0].text[:100])
                else:
                    results.append((tool, time.monotonic() - started))
            except Exception as exc:  # noqa: BLE001 — считаем любые сбои
                errors.append(repr(exc)[:100])
            await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--rps", type=float, default=10)
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--clients", type=int, default=10)
    parser.add_argument("--key", action="append", default=[], help="персональный ключ mpk_… (можно несколько)")
    args = parser.parse_args()

    interval = args.clients / args.rps
    until = time.monotonic() + args.seconds
    results: list[tuple[str, float]] = []
    errors: list[str] = []
    keys = args.key or [None]
    await asyncio.gather(
        *(worker(args.url, keys[i % len(keys)], interval, until, results, errors) for i in range(args.clients))
    )

    total = len(results) + len(errors)
    print(f"запросов: {total} за {args.seconds:.0f} с ({total / args.seconds:.1f}/с), ошибок: {len(errors)}")
    for tool in sorted({t for t, _ in results}):
        times = sorted(d for t, d in results if t == tool)
        p95 = times[min(len(times) - 1, int(len(times) * 0.95))]
        print(f"  {tool}: {len(times)} шт., медиана {statistics.median(times) * 1000:.0f} мс, p95 {p95 * 1000:.0f} мс, макс {times[-1] * 1000:.0f} мс")
    for error in sorted(set(errors))[:5]:
        print("  ошибка:", error)
    return 1 if errors else 0


if __name__ == "__main__":
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    raise SystemExit(asyncio.run(main(), loop_factory=loop_factory))
