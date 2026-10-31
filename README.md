# Mospolytech MCP

**Русский** · [English](README.en.md)

[![CI](https://github.com/EDeev/mospolytech-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/EDeev/mospolytech-mcp/actions/workflows/ci.yml)
[![Deploy prod](https://github.com/EDeev/mospolytech-mcp/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/EDeev/mospolytech-mcp/actions/workflows/deploy-prod.yml)
[![Release](https://img.shields.io/github/v/release/EDeev/mospolytech-mcp)](https://github.com/EDeev/mospolytech-mcp/releases/latest)
[![Image](https://img.shields.io/badge/ghcr.io-edeev%2Fmospolytech--mcp-2496ED?logo=docker&logoColor=white)](https://github.com/EDeev/mospolytech-mcp/pkgs/container/mospolytech-mcp)

MCP-сервер, через который LLM-агент (Claude Desktop, Claude Code или другой MCP-клиент) читает расписание Московского
Политеха и личный кабинет студента: оценки, уведомления, платежи, заявки, сообщения.

**Статус:** учебный командный проект («Автоматизация процессов жизненного цикла программных средств»,
Московский Политех, гр. 241-327, 2026), завершён · работает на стендах команды test / stage / prod

Вопрос «Какие пары у 241-327 в понедельник?» агент превращает в вызов инструмента (ответ prod-стенда):

```text
group_schedule(group="241-327", date="понедельник")
{
  "group": "241-327", "kind": "семестр", "date": "2026-11-02", "weekday": "понедельник",
  "lessons": [
    {"pair": 3, "time": "12:20–13:50", "subject": "Проектная деятельность", "type": "Практика",
     "location": "ПД", "period": "01.09.2026–03.01.2027", "link": "https://docs.google.com/…"}
  ],
  "source": "кэш", "fetched_at": "2026-10-31T18:25:43+00:00"
}
```

**Стек:** Python 3.14 · MCP SDK · SQLAlchemy 2 (async) · Alembic · PostgreSQL 17 · Docker · GitHub Actions

## Возможности

21 инструмент, подробно — [`docs/tools.md`](docs/tools.md).

- **Открытые данные, без входа:** список групп, расписание группы и преподавателя (семестр или сессия,
  на день — «завтра», «пятница», «08.10»). Расписание преподавателя сервер собирает сам из расписаний всех
  групп: у источника такого запроса нет.
- **Вход в личный кабинет:** `lk_login` или страница `/login` — пароль не сохраняется, токены ЛК лежат в БД
  зашифрованными, клиент получает персональный ключ `mpk_…`.
- **Личный кабинет:** профиль, личное расписание, успеваемость, уведомления с пометкой новых, платежи,
  заявки, диалоги, отправка сообщений.
- **История:** что менялось в оценках, платежах и заявках между проверками.
- **Отслеживаемые группы:** чужие группы, расписание которых видно рядом со своим.
- **Устойчивость:** если ЛК или rasp.dmami.ru не отвечает, отдаются данные из кэша с пометкой `stale`;
  каждое обращение к ЛК пишется в журнал; `/health` — для мониторинга.

## Быстрый старт

Готовый образ из GitHub Container Registry и PostgreSQL рядом. Нужны Docker и docker compose v2.

```bash
curl -O https://raw.githubusercontent.com/EDeev/mospolytech-mcp/main/deploy/docker-compose.yaml
cat > .env <<EOF
POSTGRES_DB=mospolytech_mcp
POSTGRES_USER=mospolytech_mcp
POSTGRES_PASSWORD=$(openssl rand -hex 16)
MCP_SECRET_KEY=$(docker run --rm ghcr.io/edeev/mospolytech-mcp:1.0.0 python -m mospolytech_mcp.crypto)
APP_TAG=1.0.0
EOF
docker compose up -d
curl http://127.0.0.1:8000/health
```

Сервис `migrate` накатывает миграции и завершается, после него стартует сервер:
`http://<адрес>:8000/mcp` — MCP, `http://<адрес>:8000/login` — вход в ЛК и готовые настройки клиента.
Теги образа: `1.0.0` и `latest` — релизы, `prod` — то, что сейчас на prod, `dev` — ветка `dev`.

Из исходников, со сборкой образа: `cp .env.example .env`, вписать `MCP_SECRET_KEY`, `make docker-up`.

## Подключение к MCP-клиенту

Откройте `http://<адрес>:8000/login`, войдите логином и паролем ЛК — страница выдаст ключ `mpk_…` и пример
настроек. Пароль идёт напрямую на сервер, LLM его не видит. Для Claude Code:

```bash
claude mcp add --transport http mospolytech http://<адрес>:8000/mcp --header "Authorization: Bearer mpk_…"
```

Открытые инструменты (группы, расписания) работают и без ключа. В Postman: New → MCP, HTTP,
`http://<адрес>:8000/mcp`.

Локально по stdio, без HTTP (после установки без Docker, см. ниже) — например, Claude Desktop,
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mospolytech": { "command": "<путь к проекту>/.venv/Scripts/mospolytech-mcp" }
  }
}
```

Настройки сервер берёт из `.env` в корне проекта; чтобы инструменты ЛК работали без `lk_login`, впишите туда
`MPU_API_KEY` (ключ с `/login`) или `MPU_LOGIN`/`MPU_PASSWORD`.

## Установка без Docker

Нужны Python 3.14 и PostgreSQL. С GNU Make (на Windows — `choco install make`):

```bash
make up          # venv, зависимости, .env, миграции, сервер по stdio
make run-http    # сервер по HTTP на 0.0.0.0:8000
make help        # остальные команды
```

На свежем клоне `make up` остановится и попросит вписать `DATABASE_URL` в `.env`; ключ шифрования —
`make secret-key`. То же без make:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env      # вписать DATABASE_URL и MCP_SECRET_KEY
.venv\Scripts\alembic upgrade head
.venv\Scripts\mospolytech-mcp --http --host 0.0.0.0 --port 8000
```

## Конфигурация

Переменные окружения (или `.env` в корне), полный список с комментариями — [`.env.example`](.env.example).

| Переменная | Что задаёт |
|---|---|
| `DATABASE_URL` | PostgreSQL, `postgresql+psycopg://user:pass@host:5432/db` |
| `MCP_SECRET_KEY` | ключ Fernet для токенов ЛК в БД — `python -m mospolytech_mcp.crypto`; сменили — все входят заново |
| `MCP_PUBLIC_URL` | адрес сервера снаружи — для подсказки с настройками на `/login` |
| `MPU_API_KEY` или `MPU_LOGIN` + `MPU_PASSWORD` | вход по умолчанию в режиме stdio (один пользователь) |
| `LK_AUTO_RELOGIN` | `1` — личный сервер одного владельца: при отказе ЛК сервер сам входит заново |
| `GROUPS_TTL_MINUTES`, `SCHEDULE_TTL_MINUTES`, `TEACHER_INDEX_TTL_MINUTES` | сроки кэша: 15 мин, 6 ч, 24 ч |
| `TEACHER_INDEX` | `0` — не собирать индекс преподавателей в фоне |
| `TEST_DATABASE_URL` | БД для интеграционных тестов (создают и удаляют временные схемы) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `APP_TAG` | docker compose |

> [!IMPORTANT]
> - `send_message` и `send_group_message` отправляют настоящие сообщения от имени студента;
>   `send_group_message` получит вся учебная группа. Отправка группе вживую не проверялась.
> - API личного кабинета неофициальный (перенесён с [MPU_LK_API](https://github.com/GODIMONGO/MPU_LK_API)):
>   если университет его поменяет, инструменты ЛК перестанут работать, а открытые данные — нет.
> - Вход по `/login` и ключи `mpk_…` защищают данные пользователя, но не сам сервер: без обратного прокси
>   с HTTPS его не стоит открывать в интернет — пароль ЛК пойдёт по HTTP открытым текстом.

## Как устроено

```
MCP-клиент (LLM) ──MCP──▶ server.py ── инструменты, ошибки → понятный ответ
                              │
             ┌────────────────┼─────────────────────────┐
             ▼                ▼                         ▼
      открытые данные     личный кабинет            хранение
      cache.py            auth.py (вход, токены,    db/ + alembic/
      teachers.py           журнал обращений)       PostgreSQL
      open_api/ (вендор)  personal.py (кэш, история)
                          lk_api/ (порт MPU_LK_API)
```

- **`open_api/`** — открытые данные rasp.dmami.ru. По ТЗ (ТПО-004) — готовая библиотека
  [mospolytech_api](https://github.com/r4nd0lph-c/mospolytech_api), завендоренная как есть, сверху
  async-обёртка.
- **`lk_api/`** — личный кабинет: по ТЗ (ТПО-005) авторизация и API перенесены с Go-библиотеки
  [MPU_LK_API](https://github.com/GODIMONGO/MPU_LK_API) на Python.
- **`cache.py`, `teachers.py`** — кэш справочных данных с откатом на него и индекс преподавателей.
- **`auth.py`, `identity.py`, `crypto.py`** — вход, шифрование токенов, ключи `mpk_…`, журнал обращений.
- **`personal.py`, `views.py`** — персональные данные: кэш, история изменений, уведомления без дублей,
  ответы в удобном для LLM виде.

Документация: [`docs/tools.md`](docs/tools.md) — инструменты, [`docs/db-schema.md`](docs/db-schema.md) —
схема БД и миграции, [`db/schema/schema.sql`](db/schema/schema.sql) — снимок схемы,
[`docs/official/lab01-tech-spec.pdf`](docs/official/lab01-tech-spec.pdf) — техническое задание (ЛР1),
[`docs/README.md`](docs/README.md) — что где лежит.

## Развёртывание

Три стенда — виртуальные машины Ubuntu (VMware): test, stage, prod. Работа идёт по GitFlow:
`feature/*` → pull request в `dev` → `dev` → `main`. Ветки `dev` и `main` защищены: только через pull
request с одобрением другого участника и зелёной сборкой.

- **CI** ([`ci.yml`](.github/workflows/ci.yml)) на каждый push: ruff, bandit, gitleaks, squawk (SQL
  миграций) → сборка образа → тесты с PostgreSQL → публикация в GHCR (`dev`, `prod`, по SHA).
- **stage** — после push в `dev`: self-hosted runner на ВМ test накатывает миграции на TEST-стенд, снимает
  схему, затем мигрирует и обновляет stage и проверяет, что схемы совпали, а `/health` отвечает.
- **prod** ([`deploy-prod.yml`](.github/workflows/deploy-prod.yml)) — после CI на `main` и ручного
  одобрения в environment `production`: резервная копия БД (`scripts/backup_db.sh`), сверка схемы с
  stage, миграция, обновление, `/health`, повторная сверка.
- **Релиз** ([`release.yml`](.github/workflows/release.yml)) — на тег `v*`: пакет (wheel, sdist) в
  GitHub Releases и образ с тегом версии и `latest`.

Миграции рассчитаны на работающую БД: индексы — `CONCURRENTLY`, ограничения — `NOT VALID` и отдельный
`VALIDATE`, изменение столбцов — по схеме expand/contract (подробнее — [`docs/db-schema.md`](docs/db-schema.md)).

## Разработка

```bash
make test        # все тесты; интеграционные — если в .env задан TEST_DATABASE_URL
make test-unit   # только офлайн, без БД и сети
make cov         # с отчётом о покрытии
ruff check .
```

Офлайн-тесты подменяют HTTP (`httpx.MockTransport` для ЛК, подмена `requests` для открытого API).
Интеграционные поднимают схему миграциями в отдельной схеме PostgreSQL и проверяют, что миграции
накатываются с нуля, откатываются и совпадают с моделями. Проверка ЛК на реальном аккаунте —
`make check-lk` (только чтение, нужны `MPU_LOGIN`/`MPU_PASSWORD`), нагрузочная —
`python scripts/load_test.py http://127.0.0.1:8000/mcp --rps 10 --seconds 30`.

Коммиты — Conventional Commits, на русском. Изменения схемы БД — только новой миграцией вместе с
обновлённым `db/schema/schema.sql`.

## Лицензия

Учебный проект («Автоматизация процессов жизненного цикла программных средств», Московский Политех,
2026/2027 учебный год) — код доступен для изучения, отдельной лицензии нет. Вендор
[mospolytech_api](https://github.com/r4nd0lph-c/mospolytech_api) в `src/mospolytech_mcp/open_api/_vendor/` —
под своей лицензией Apache 2.0 (`LICENSE.md`, `NOTICE.md` там же).

## Авторы

- **Деев Егор** — [GitHub](https://github.com/EDeev)
- **Шмыговский Никита** — [GitHub](https://github.com/Bulbak1)
- **Старков Руслан** — [GitHub](https://github.com/RayStar-k)

---

<div align="center">
  <sub>⭐ Если проект оказался полезным, поставьте звёздочку на GitHub!</sub>
  <p><sub>Сделано с ❤️ студентами Московского Политеха, гр. 241-327</sub></p>
</div>
