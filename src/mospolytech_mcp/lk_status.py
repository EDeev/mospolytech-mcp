# Проверка доступности личного кабинета.
import requests


def lk_available(url: str = "https://e.mospolytech.ru/") -> bool:
    return requests.get(url, timeout=5, verify=False).ok
