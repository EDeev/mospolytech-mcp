# Mospolytech MCP

Наш учебный проект по дисциплине «Автоматизация процессов жизненного цикла
программных средств» (Московский Политех, гр. 241–327). Делаем MCP-сервер,
который даёт LLM-агенту (например, Claude) доступ к данным университета —
и к открытому справочнику (группы, расписание), и к личному кабинету
конкретного авторизованного пользователя (расписание, оценки, уведомления,
платежи, заявки, сообщения).

Команда — три человека:

- Деев Егор Викторович
- Шмыговский Никита Сергеевич
- Старков Руслан Владимирович

Официальное техническое задание, которое сдавали на лаб. №1 —
[`docs/official/lab01-tech-spec.pdf`](docs/official/lab01-tech-spec.pdf).
Наш рабочий план по всем 8 лабораторным (архитектура, черновая схема БД,
открытые риски) — [`docs/working/plan.md`](docs/working/plan.md). Подробнее
про то, как мы делим документацию на официальную и рабочую — в
[`docs/README.md`](docs/README.md).

## Что уже есть

Мы собрали обе половины университетского API в этот репозиторий и
объединили их в один объект `UniversityAPI`, чтобы MCP-серверу (и нам
самим) не приходилось таскать два клиента порознь:

```python
from mospolytech_mcp import UniversityAPI

async with UniversityAPI() as uni:
    groups = await uni.open.get_groups()          # открытые данные, без авторизации
    await uni.lk.login(login, password)             # а тут уже личный кабинет
    my_schedule = await uni.lk.get_my_schedule()
```

- **`open_api`** — открытые справочные данные университета. По ТЗ (ТПО-004)
  здесь используется готовая библиотека
  [mospolytech_api](https://github.com/r4nd0lph-c/mospolytech_api), а не
  наша реализация — мы завендорили её код как есть в `open_api/_vendor/` и
  сверху накрутили тонкую async-обёртку (`asyncio.to_thread`), чтобы она не
  блокировала event loop рядом с остальным асинхронным кодом.
- **`lk_api`** — личный кабинет. Тут по ТЗ (ТПО-005) наоборот: логику
  авторизации и работы с API переносим с существующей Go-библиотеки
  [MPU_LK_API](https://github.com/GODIMONGO/MPU_LK_API) на Python, своими
  руками. Сделали: логин/логаут/обновление токенов (обе системы — легаси
  token и JWT+refresh), расписание, успеваемость, платежи и договоры,
  заявки, уведомления и объявления, диалоги и (осторожно,
  неподтверждено — см. `docs/working/plan.md`) отправку сообщений.

Сам MCP-сервер (`server.py`) уже запускается и отвечает на первый
инструмент — `list_groups` (ФОД-001), через полный стек: протокол MCP →
`UniversityAPI.open` → кэш в PostgreSQL (`cache.py` + `db/`, миграции
Alembic в `alembic/`). Живьём проверяли: 592 группы забрались с
rasp.dmami.ru, записались в БД, второй вызов уже идёт из кэша. Остальные
инструменты (ФЛК-*, оставшиеся ФХД) дописываем по плану в
`docs/working/plan.md`, раздел 3.1.

## Требования

- Python 3.14 (у нас работает через `py -3.14`)
- Доступ к PostgreSQL — свой пользователь `mospolytech_mcp` на общем сервере
  команды (не `postgres`/admin), спросите данные в чате, если не сохранили

## Быстрый старт

Если стоит GNU Make (на Windows — `choco install make`), всё поднимается
одной командой:

```powershell
make up
```

Она создаёт `.venv`, ставит зависимости, копирует `.env.example` в `.env`,
накатывает миграции и запускает сервер. На свежем клоне первый запуск
остановится с просьбой вписать `DATABASE_URL` в `.env` — впишите и
запустите `make up` ещё раз. Остальные команды (`make test`, `make migrate`,
`make run`, `make check-lk`, `make clean`) — в `make help`. Работает из
PowerShell, cmd и Git Bash, а также на Linux/macOS.

Ниже — то же самое руками, без make.

## Установка

```powershell
py -3.14 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env
# впишите DATABASE_URL (и MPU_LOGIN/MPU_PASSWORD, если нужен check_lk_api.py)
.venv\Scripts\alembic upgrade head
```

## Тесты

Всё, что не требует реального логина, покрыто офлайн-тестами — сеть не
трогаем, HTTP подменяем (`httpx.MockTransport` для `lk_api`, подмена
`requests.get` для `open_api`):

```powershell
.venv\Scripts\python -m pytest -q
```

## Проверка на реальном аккаунте

`open_api` не требует авторизации, поэтому его можно проверить вживую хоть
прямо сейчас (реальный запрос к rasp.dmami.ru, без секретов):

```powershell
.venv\Scripts\python -c "import asyncio; from mospolytech_mcp.open_api import OpenDataClient; asyncio.run(OpenDataClient().get_groups())"
```

Для `lk_api` нужен свой логин/пароль от e.mospolytech.ru — впишите
MPU_LOGIN и MPU_PASSWORD в свой `.env`, дальше `scripts/check_lk_api.py`
логинится и читает профиль, расписание, успеваемость, уведомления,
платежи, заявки и диалоги (ничего не меняет):

```powershell
.venv\Scripts\python scripts\check_lk_api.py
```

Пароль используется один раз при вызове `login()` и нигде не сохраняется.
`.env` в `.gitignore`, в репозиторий не попадёт.

## Запуск сервера

```powershell
.venv\Scripts\python -m mospolytech_mcp.server
```

Поднимается на stdio-транспорте — так подключается локальный MCP-клиент
(например, Claude Desktop/Code). Пока один инструмент, `list_groups`
(ФОД-001) — список групп с кэшем в БД на 15 минут.

### HTTP-режим

Если сервер крутится в VM или на другой машине, stdio не подходит —
есть HTTP-режим (streamable HTTP, эндпоинт `/mcp`):

```bash
make run-http            # 0.0.0.0:8000
make run-http PORT=9000  # HOST и PORT можно переопределить
```

Без make: `python -m mospolytech_mcp.server --http --host 0.0.0.0 --port 8000`.

В Postman: New → MCP, транспорт HTTP, URL `http://<адрес VM>:8000/mcp`,
Connect — в списке инструментов появится `list_groups`, его можно вызвать
прямо оттуда. Авторизации на сервере нет, так что наружу (`0.0.0.0`)
открывать только на тестовой машине.

## Docker

Тот же сервер, но в контейнере и со своей PostgreSQL рядом — так он живёт
на ВМ начиная с ЛР3. Нужны Docker и docker compose v2, `.env` и venv не
нужны:

```bash
make docker-up      
make docker-logs   
make docker-down    
```

Что происходит:

- `Dockerfile` собирает образ из исходников: `python:3.14-slim`, отдельным
  слоем зависимости из `pyproject.toml`, потом сам пакет. При старте
  контейнер накатывает миграции (`alembic upgrade head`) и запускает сервер
  в HTTP-режиме на `0.0.0.0:8000` — снаружи это `http://<адрес>:8000/mcp`.
- `docker-compose.yaml` поднимает два сервиса: `db` (`postgres:17-alpine`)
  и `mcp` (наш образ). Сервер стартует только после того, как БД ответила на
  `pg_isready`, и ходит к ней по имени `db` внутри сети compose — наружу
  порт PostgreSQL не выставлен. `DATABASE_URL` для контейнера compose
  собирает сам из `POSTGRES_*`; `.env` в образ не попадает (`.dockerignore`).
- Файлы БД лежат в volume `pgdata`, поэтому `docker compose down` и
  повторный `up` данные не теряют. Снести вместе с данными —
  `docker compose down -v`.

Логин, пароль и имя БД по умолчанию `mospolytech_mcp`; переопределяются через
`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` в `.env` — compose читает
его сам, а `DATABASE_URL` оттуда для контейнера не используется.

Посмотреть, что кэш реально лёг в контейнерную БД (это же удобно показывать
после рестарта):

```bash
docker compose exec db psql -U mospolytech_mcp -c "select id, jsonb_array_length(groups), fetched_at from groups_cache"
```

## Структура репозитория

```
docs/
  official/       — официальные документы для сдачи (ТЗ и т.д.), PDF, не правим задним числом
  working/        — наш рабочий план, заметки, черновики — правим постоянно
  sdo/            — методички по всем 8 лабораторным и справочные ГОСТ/IEEE из СДО
src/mospolytech_mcp/
  api.py          — UniversityAPI, точка входа: держит open_api + lk_api вместе
  server.py       — сам MCP-сервер (регистрация tools)
  cache.py        — кэширующие обёртки над UniversityAPI, пишут в БД (ФХД-003)
  open_api/       — открытые данные (вендор mospolytech_api + наша async-обёртка)
  lk_api/         — личный кабинет (наш порт MPU_LK_API с Go на Python)
  db/             — модели SQLAlchemy (схема версионируется в alembic/)
alembic/          — миграции БД (alembic upgrade head накатывает схему)
tests/            — офлайн-тесты (pytest, без сети)
scripts/          — ручные проверочные скрипты (против реального ЛК)
Dockerfile        — образ сервера (сборка из исходников, миграции + HTTP-режим на старте)
docker-compose.yaml — сервер + PostgreSQL с volume для данных
```
