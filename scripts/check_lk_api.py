# Ручная офлайн-проверка LKClient на реальном аккаунте (MPU_LOGIN/MPU_PASSWORD).

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mospolytech_mcp._dotenv import load_dotenv  # noqa: E402
from mospolytech_mcp.lk_api import LKClient, LKError  # noqa: E402


async def main() -> int:
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")

    login = os.environ.get("MPU_LOGIN")
    password = os.environ.get("MPU_PASSWORD")
    if not login or not password:
        print(
            "Не заданы MPU_LOGIN / MPU_PASSWORD (переменные окружения или .env).",
            file=sys.stderr,
        )
        return 1

    async with LKClient() as client:
        print(f"[1/9] Авторизация как {login}...")
        try:
            tokens = await client.login(login, password)
        except LKError as e:
            print(f"  ОШИБКА логина: {e}")
            return 1
        print(f"  OK: token={tokens.token[:12]}..., jwt={'есть' if tokens.jwt else 'нет'}")

        print("[2/9] get_user()...")
        try:
            user = await client.get_user()
            print(f"  OK: {user.surname} {user.name}, группа {user.group}, курс {user.course}")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[3/9] get_my_schedule()...")
        try:
            schedule = await client.get_my_schedule()
            print(f"  OK: {len(schedule)} дней в ответе")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[4/9] get_academic_performance(semester=1)...")
        try:
            perf = await client.get_academic_performance(1)
            print(f"  OK: {len(perf)} записей")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[5/9] get_notifications()...")
        try:
            notifications = await client.get_notifications()
            print(f"  OK: {len(notifications)} уведомлений")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[6/9] get_alerts()...")
        try:
            alerts = await client.get_alerts()
            print(f"  OK: {len(alerts)} объявлений")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[7/9] get_payments()...")
        try:
            payments = await client.get_payments()
            print(
                f"  OK: {len(payments.education)} договоров об обучении, "
                f"{len(payments.dormitory)} по общежитию"
            )
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[8/9] get_app_requests()...")
        try:
            requests_ = await client.get_app_requests()
            print(f"  OK: {len(requests_)} заявок")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

        print("[9/9] get_dialogues()...")
        try:
            dialogues = await client.get_dialogues()
            print(f"  OK: {len(dialogues)} диалогов")
        except LKError as e:
            print(f"  ОШИБКА: {e}")

    print("\nГотово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
