# Mospolytech MCP

[Русский](README.md) · **English**

[![CI](https://github.com/EDeev/mospolytech-mcp/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/EDeev/mospolytech-mcp/actions/workflows/ci.yml)
[![Deploy prod](https://github.com/EDeev/mospolytech-mcp/actions/workflows/deploy-prod.yml/badge.svg)](https://github.com/EDeev/mospolytech-mcp/actions/workflows/deploy-prod.yml)
[![Release](https://img.shields.io/github/v/release/EDeev/mospolytech-mcp)](https://github.com/EDeev/mospolytech-mcp/releases/latest)
[![Image](https://img.shields.io/badge/ghcr.io-edeev%2Fmospolytech--mcp-2496ED?logo=docker&logoColor=white)](https://github.com/EDeev/mospolytech-mcp/pkgs/container/mospolytech-mcp)

An MCP server that lets an LLM agent (Claude Desktop, Claude Code or any other MCP client) read the Moscow
Polytechnic University timetable and a student's personal account: grades, notifications, payments,
requests, messages.

**Status:** team coursework project ("Software Life Cycle Process Automation", Moscow Polytechnic University,
group 241-327, 2026), completed · runs on the team's test / stage / prod environments

The question "What classes does 241-327 have on Monday?" becomes a tool call (response from prod; the
server answers in Russian):

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

**Stack:** Python 3.14 · MCP SDK · SQLAlchemy 2 (async) · Alembic · PostgreSQL 17 · Docker · GitHub Actions

## Features

21 tools, described in [`docs/tools.md`](docs/tools.md) (in Russian).

- **Open data, no login:** group list, group and teacher timetables (semester or exam session, for a day —
  "tomorrow", "Friday", "08.10", in Russian). The server builds teacher timetables itself from the timetables
  of all groups, since the source has no such query.
- **Personal account login:** `lk_login` or the `/login` page. The password is never stored, account tokens
  are encrypted in the database, and the client gets a personal key `mpk_…`.
- **Personal account:** profile, personal timetable, grades, notifications with new ones marked, payments,
  requests, dialogs, sending messages.
- **History:** what changed in grades, payments and requests between checks.
- **Tracked groups:** other groups whose timetable is shown next to your own.
- **Resilience:** if the personal account or rasp.dmami.ru is down, cached data is returned marked `stale`;
  every personal account call is logged; `/health` for monitoring.

## Quick start

The prebuilt image from GitHub Container Registry with PostgreSQL next to it. Requires Docker and docker
compose v2.

```bash
curl -O https://raw.githubusercontent.com/EDeev/mospolytech-mcp/main/deploy/docker-compose.yaml
cat > .env <<EOF
POSTGRES_DB=mospolytech_mcp
POSTGRES_USER=mospolytech_mcp
POSTGRES_PASSWORD=$(openssl rand -hex 16)
MCP_SECRET_KEY=$(docker run --rm ghcr.io/edeev/mospolytech-mcp:1.0.1 python -m mospolytech_mcp.crypto)
APP_TAG=1.0.1
EOF
docker compose up -d
curl http://127.0.0.1:8000/health
```

The `migrate` service applies the migrations and exits, then the server starts: `http://<host>:8000/mcp` is
MCP, `http://<host>:8000/login` is the personal account login with ready-made client settings. Image tags:
a version number (`1.0.1`) and `latest` are releases, `prod` is what runs on prod now, `dev` is the `dev` branch.

From source, building the image: `cp .env.example .env`, set `MCP_SECRET_KEY`, `make docker-up`.

## Connecting an MCP client

Open `http://<host>:8000/login` and sign in with your personal account login and password. The page gives
you an `mpk_…` key and a settings example. The password goes straight to the server; the LLM never sees it.
For Claude Code:

```bash
claude mcp add --transport http mospolytech http://<host>:8000/mcp --header "Authorization: Bearer mpk_…"
```

Open-data tools (groups, timetables) work without a key. In Postman: New → MCP, HTTP,
`http://<host>:8000/mcp`.

Locally over stdio, without HTTP (after installing without Docker, see below), e.g. Claude Desktop,
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mospolytech": { "command": "<project path>/.venv/Scripts/mospolytech-mcp" }
  }
}
```

The server reads settings from `.env` in the project root. For the personal account tools to work without
`lk_login`, put `MPU_API_KEY` (the key from `/login`) or `MPU_LOGIN`/`MPU_PASSWORD` there.

## Installing without Docker

Requires Python 3.14 and PostgreSQL. With GNU Make (on Windows: `choco install make`):

```bash
make up          # venv, dependencies, .env, migrations, server over stdio
make run-http    # server over HTTP on 0.0.0.0:8000
make help        # other commands
```

On a fresh clone `make up` stops and asks you to set `DATABASE_URL` in `.env`; the encryption key comes from
`make secret-key`. The same without make:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env      # set DATABASE_URL and MCP_SECRET_KEY
.venv\Scripts\alembic upgrade head
.venv\Scripts\mospolytech-mcp --http --host 0.0.0.0 --port 8000
```

## Configuration

Environment variables (or `.env` in the root); the full commented list is in [`.env.example`](.env.example).

| Variable | Sets |
|---|---|
| `DATABASE_URL` | PostgreSQL, `postgresql+psycopg://user:pass@host:5432/db` |
| `MCP_SECRET_KEY` | Fernet key for account tokens in the database (`python -m mospolytech_mcp.crypto`); changing it signs everyone out |
| `MCP_PUBLIC_URL` | the server's external address, for the settings hint on `/login` |
| `MPU_API_KEY` or `MPU_LOGIN` + `MPU_PASSWORD` | default login in stdio mode (single user) |
| `LK_AUTO_RELOGIN` | `1` for a personal single-owner server: when the account rejects the session, the server logs in again itself |
| `GROUPS_TTL_MINUTES`, `SCHEDULE_TTL_MINUTES`, `TEACHER_INDEX_TTL_MINUTES` | cache lifetimes: 15 min, 6 h, 24 h |
| `TEACHER_INDEX` | `0` disables the background teacher index |
| `TEST_DATABASE_URL` | database for integration tests (they create and drop temporary schemas) |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `APP_TAG` | docker compose |

> [!IMPORTANT]
> - `send_message` and `send_group_message` send real messages on the student's behalf; `send_group_message`
>   reaches the whole study group. Sending to a group has not been tested live.
> - The personal account API is unofficial (ported from [MPU_LK_API](https://github.com/GODIMONGO/MPU_LK_API)):
>   if the university changes it, the personal account tools stop working; open data keeps working.
> - The `/login` page and `mpk_…` keys protect the user's data, not the server itself: do not expose it to the
>   internet without a reverse proxy with HTTPS, or the account password travels over plain HTTP.

## How it works

```
MCP client (LLM) ──MCP──▶ server.py ── tools, errors → readable answer
                              │
             ┌────────────────┼─────────────────────────┐
             ▼                ▼                         ▼
      open data           personal account          storage
      cache.py            auth.py (login, tokens,   db/ + alembic/
      teachers.py           access log)             PostgreSQL
      open_api/ (vendor)  personal.py (cache, history)
                          lk_api/ (port of MPU_LK_API)
```

- **`open_api/`** — open data from rasp.dmami.ru. As the spec requires (ТПО-004), it is the existing
  [mospolytech_api](https://github.com/r4nd0lph-c/mospolytech_api) library, vendored as is, with an async
  wrapper on top.
- **`lk_api/`** — personal account: as the spec requires (ТПО-005), authorization and API calls were ported
  from the Go library [MPU_LK_API](https://github.com/GODIMONGO/MPU_LK_API) to Python.
- **`cache.py`, `teachers.py`** — reference data cache with fallback to it, and the teacher index.
- **`auth.py`, `identity.py`, `crypto.py`** — login, token encryption, `mpk_…` keys, access log.
- **`personal.py`, `views.py`** — personal data: cache, change history, notifications without duplicates,
  answers shaped for an LLM.

Documentation (in Russian): [`docs/tools.md`](docs/tools.md) — tools, [`docs/db-schema.md`](docs/db-schema.md) —
database schema and migrations, [`db/schema/schema.sql`](db/schema/schema.sql) — schema snapshot,
[`docs/official/lab01-tech-spec.pdf`](docs/official/lab01-tech-spec.pdf) — technical specification,
[`docs/README.md`](docs/README.md) — what is where.

## Deployment

Three environments, Ubuntu virtual machines (VMware): test, stage, prod. Work follows GitFlow: `feature/*` →
pull request into `dev` → `dev` → `main`. The `dev` and `main` branches are protected: pull requests only,
with another member's approval and a green build.

- **CI** ([`ci.yml`](.github/workflows/ci.yml)) on every push: ruff, bandit, gitleaks, squawk (migration
  SQL) → image build → tests with PostgreSQL → publishing to GHCR (`dev`, `prod`, by SHA).
- **stage** — after a push to `dev`: a self-hosted runner on the test VM migrates the TEST environment, dumps
  its schema, then migrates and updates stage and checks that the schemas match and `/health` responds.
- **prod** ([`deploy-prod.yml`](.github/workflows/deploy-prod.yml)) — after CI on `main` and manual approval
  in the `production` environment: database backup (`scripts/backup_db.sh`), schema check against stage,
  migration, update, `/health`, second schema check.
- **Release** ([`release.yml`](.github/workflows/release.yml)) — on a `v*` tag: the package (wheel, sdist) in
  GitHub Releases and the image tagged with the version and `latest`.

Migrations are written for a live database: indexes `CONCURRENTLY`, constraints `NOT VALID` plus a separate
`VALIDATE`, column changes by expand/contract (details in [`docs/db-schema.md`](docs/db-schema.md)).

## Development

```bash
make test        # all tests; integration tests if TEST_DATABASE_URL is set in .env
make test-unit   # offline only, no database or network
make cov         # with a coverage report
ruff check .
```

Offline tests stub HTTP (`httpx.MockTransport` for the personal account, a `requests` stub for open data).
Integration tests build the schema with migrations in a separate PostgreSQL schema and check that migrations
apply from scratch, roll back fully and match the models. A live personal account check is
`make check-lk` (read-only, needs `MPU_LOGIN`/`MPU_PASSWORD`); a load test is
`python scripts/load_test.py http://127.0.0.1:8000/mcp --rps 10 --seconds 30`.

Commits follow Conventional Commits, in Russian. Schema changes go only through a new migration together with
an updated `db/schema/schema.sql`.

## License

Coursework project ("Software Life Cycle Process Automation", Moscow Polytechnic University, academic year
2026/2027). The code is open for study; there is no separate license. The vendored
[mospolytech_api](https://github.com/r4nd0lph-c/mospolytech_api) in `src/mospolytech_mcp/open_api/_vendor/`
keeps its own Apache 2.0 license (`LICENSE.md`, `NOTICE.md` there).

## Authors

- **Egor Deev** — [GitHub](https://github.com/EDeev)
- **Nikita Shmygovsky** — [GitHub](https://github.com/Bulbak1)
- **Ruslan Starkov** — [GitHub](https://github.com/RayStar-k)

---

<div align="center">
  <sub>⭐ If you find this project useful, give it a star on GitHub!</sub>
  <p><sub>Made with ❤️ by students of Moscow Polytechnic University, group 241-327</sub></p>
</div>
