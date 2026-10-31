# Подделки внешних источников для тестов: открытое API расписаний и личный кабинет (через httpx.MockTransport).

from __future__ import annotations

import copy
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from mospolytech_mcp.lk_api import LKClient

GROUPS = ["221-111", "241-327", "241-328"]
# id диалогов в настоящем ЛК длинные — «messages:<id>» не влезает в lk_access_log.action без обрезки
DIALOG_ID = "dlg-" + "7f3c9a1e" * 8


def event(title: str, teachers: list[str], dates: list[str], *, rooms=("Пр 2413",), type_="Лекция") -> dict:
    return {
        "title": title,
        "type": type_,
        "teachers": teachers,
        "location": "Прянишникова",
        "rooms": list(rooms),
        "link": None,
        "dates": dates,
    }


def semester(group: str) -> dict[str, Any]:
    """Расписание в формате mospolytech_api.get_schedule: сетка 6 дней × 7 пар."""
    grid = [[[] for _ in range(7)] for _ in range(6)]
    # вторник, 5-я пара — общий поток у 241-327 и 241-328
    if group in ("241-327", "241-328"):
        grid[1][4].append(event("Разработка мобильных приложений", ["Васильев Денис Борисович"], ["01.09.2026", "01.11.2026"]))
    # четверг, 1-я пара — только у 241-327
    if group == "241-327":
        grid[3][0].append(
            event("Базы данных", ["Бритвина Валентина Валентиновна", "Баринова Наталья Владимировна"], ["01.09.2026", "03.01.2027"], type_="Практика")
        )
    if group == "221-111":
        grid[0][2].append(event("Физика", ["Васильева Анна Петровна"], ["01.09.2026", "03.01.2027"]))
    return {"group": group, "type": "morning", "is_session": False, "dates": ["01.09.2026", "10.01.2027"], "grid": grid}


def session_file() -> dict[str, Any]:
    """Файл сессии в формате mospolytech_api.get_session: группа → сетка по датам."""
    day = [[] for _ in range(7)]
    day[2].append(event("Базы данных", ["Бритвина Валентина Валентиновна"], ["15.01.2027", "15.01.2027"], type_="Экзамен"))
    return {"241-327": {"type": "morning", "dates": ["10.01.2027", "31.01.2027"], "grid": [day]}}


class BadRequest(Exception):
    pass


class FakeOpenData:
    def __init__(self) -> None:
        self.down = False
        self.calls: list[tuple] = []

    def _check(self) -> None:
        if self.down:
            raise ConnectionError("rasp.dmami.ru не отвечает")

    async def get_groups(self) -> list[str]:
        self.calls.append(("groups",))
        self._check()
        return list(GROUPS)

    async def get_schedule(self, group: str, *, is_session: bool = False) -> dict:
        self.calls.append(("schedule", group, is_session))
        self._check()
        if group not in GROUPS or is_session:
            raise ValueError(f"The schedule for the '{group}' group does not exist.")
        return semester(group)

    async def get_session(self) -> dict:
        self.calls.append(("session",))
        self._check()
        return session_file()


class FakeLK:
    """Минимальный личный кабинет: old-e.mospolytech.ru/lk_api.php + api.mospolytech.ru."""

    LOGIN = "deev.e.v"
    PASSWORD = "secret"

    def __init__(self) -> None:
        self.down = False
        self.token = "legacy-token"
        self.requests: list[str] = []
        self.sent: list[dict[str, str]] = []
        self.grade = "Хорошо"
        self.notifications = [{"id": "n1", "type": "info", "title": "Справка готова", "text": "Заберите в 1-й кабинет"}]
        self.alerts = [{"id": "a1", "title": "День открытых дверей", "content": "в субботу", "date": "2026-10-10", "time": "12:00"}]

    def factory(self) -> LKClient:
        return LKClient(http_client=httpx.AsyncClient(transport=httpx.MockTransport(self.handle)))

    def handle(self, request: httpx.Request) -> httpx.Response:
        url = urlsplit(str(request.url))
        query = url.query
        self.requests.append(f"{request.method} {url.path}?{query.split('&token=')[0]}")
        if self.down:
            return httpx.Response(502, text="Bad Gateway")

        if url.path == "/auth/token/reissue":
            return httpx.Response(200, json={"access_token": "jwt-2", "refresh_token": "refresh-2"})
        if url.path in ("", "/") and request.method == "POST":
            return httpx.Response(200, text="")
        if url.path != "/lk_api.php":
            return httpx.Response(404)

        if request.method == "POST" and not query:
            form = parse_qs(request.content.decode())
            if form.get("ulogin") == [self.LOGIN] and form.get("upassword") == [self.PASSWORD]:
                return httpx.Response(200, json={"token": self.token, "jwt": "jwt-1", "jwt_refresh": "refresh-1", "guid": "guid-deev"})
            return httpx.Response(400, text="")

        params = parse_qs(query, keep_blank_values=True)
        if params.get("token") != [self.token]:
            return httpx.Response(400, text="")  # так настоящий ЛК отвечает на протухший токен
        try:
            answer = self.answer(request, params)
        except BadRequest:
            return httpx.Response(400, text="")  # и на неверный запрос — тоже
        return httpx.Response(200, content=json.dumps(answer, ensure_ascii=False).encode())

    def answer(self, request: httpx.Request, params: dict[str, list[str]]) -> Any:
        if "getUser" in params:
            return {"user": {"id": 77, "name": "Егор", "surname": "Деев", "patronymic": "Викторович", "group": "241-327", "course": "3", "avatar": "x.png"}}
        if "getSchedule" in params:
            if params.get("session") == ["1"]:
                return {"2027-01-15": {"lessons": [{"name": "Базы данных (экзамен)", "timeInterval": "12:20 - 13:50"}]}}
            # как в настоящем ЛК: ключи — дни недели по-английски, период занятия — «01 Сен - 01 Ноя»
            return {
                "Tuesday": {"lessons": [
                    {"name": "Разработка мобильных приложений", "timeInterval": "16:10 - 17:40", "teachers": ["Васильев Д. Б."], "dateInterval": "01 Сен - 01 Ноя"},
                    {"name": "Разработка мобильных приложений (лаб.)", "timeInterval": "16:10 - 17:40", "dateInterval": "02 Ноя - 03 Янв"},
                ]},
                "Thursday": {"lessons": [{"name": "Базы данных", "timeInterval": "9:00 - 10:30", "dateInterval": "01 Сен - 03 Янв"}]},
            }
        if "getAcademicPerformance" in params:
            return {"academicPerformance": [
                {"id": "p1", "name": "Базы данных", "exam_type": "Экзамен", "grade": self.grade, "semestr": params["semestr"][0]},
                {"id": "p2", "name": "Физкультура", "exam_type": "Зачёт", "grade": "Зачтено"},
            ]}
        if "getNotifications" in params:
            return copy.deepcopy(self.notifications)
        if "getAlerts" in params:
            return copy.deepcopy(self.alerts)
        if "getPayments" in params:
            return {"contracts": {"education": [{"id": "c1", "number": "Д-1", "name": "Обучение", "balance": "0", "payments": [{"date": "2026-09-01", "value": "100000"}]}], "dormitory": []}}
        if "getAppRequests" in params:
            return [{"id": "r1", "num": "15", "subject": "Справка об обучении", "status": "Готово"}]
        if "getMsgDialogues" in params:
            return [{"id": DIALOG_ID, "subject": "Курсовая", "opponent": {"name": "Васильев Д. Б."}, "lastmessage": {"from": "Васильев Д. Б.", "text": "Жду черновик"}}]
        if "getMessagesInDialogue" in params:
            # как настоящий ЛК — от новых к старым
            return [
                {"author_name": "Васильев Д. Б.", "msg_id": str(i), "html": f"<p>сообщение&nbsp;{i}</p>", "datetime": f"2026-10-0{i + 1} 10:00:00"}
                for i in reversed(range(5))
            ]
        if "getGroupChat" in params:
            return {"link": "https://t.me/+group241327"}
        if "newMessage" in params:
            content_type = request.headers.get("content-type", "")
            target = next((k for k in ("to_dialogue", "to_group", "to_id") if k in params), None)
            if "multipart/form-data" not in content_type or target is None:
                raise BadRequest()
            text = request.content.decode().split('name="text"', 1)[1].split("\r\n\r\n", 1)[1].split("\r\n--", 1)[0]
            self.sent.append({target: params[target][0], "text": text})
            return {"status": "ok"}
        return None
