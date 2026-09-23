ifeq ($(OS),Windows_NT)
SHELL := cmd.exe
SYS_PYTHON ?= py -3.14
VENV_PIP := .venv/Scripts/pip.exe
PY := .venv\Scripts\python.exe
else
SYS_PYTHON ?= python3.14
VENV_PIP := .venv/bin/pip
PY := .venv/bin/python
endif

STAMP := .venv/.installed

HOST ?= 0.0.0.0
PORT ?= 8000

.DEFAULT_GOAL := help
.PHONY: help up setup install check-env migrate run run-http test check-lk clean docker-up docker-down docker-logs

help: 
	@$(SYS_PYTHON) -X utf8 -c "import re, sys; [print('  make {:<12} {}'.format(*m.groups())) for m in re.finditer(r'^([a-z-]+):.*?## (.*)', open(sys.argv[1], encoding='utf-8').read(), re.M)]" $(firstword $(MAKEFILE_LIST))

up: migrate run ## всё сразу: окружение, .env, миграции, сервер

setup: install .env ## venv, зависимости и .env

install: $(STAMP) ## venv и зависимости

$(VENV_PIP):
	$(SYS_PYTHON) -m venv .venv

$(STAMP): $(VENV_PIP) pyproject.toml
	$(PY) -m pip install -e ".[dev]"
	@$(PY) -c "import pathlib; pathlib.Path('$(STAMP)').touch()"

.env:
	@$(SYS_PYTHON) -c "import shutil; shutil.copy('.env.example', '.env')"
	@echo .env created from .env.example - fill in DATABASE_URL 1>&2

check-env: $(STAMP) .env
	@$(PY) -c "import os, sys, pathlib; from mospolytech_mcp._dotenv import load_dotenv; load_dotenv(pathlib.Path('.env')); sys.exit(None if os.environ.get('DATABASE_URL') else 'DATABASE_URL is empty - fill it in .env and run make again')"

migrate: check-env ## миграции БД
	$(PY) -m alembic upgrade head

# stdout занят протоколом, поэтому echo в stderr
run: check-env ## запустить MCP-сервер (stdio)
	@echo mospolytech-mcp is running on stdio, Ctrl+C to stop 1>&2
	@$(PY) -m mospolytech_mcp.server

run-http: check-env ## сервер по HTTP, http://HOST:PORT/mcp
	$(PY) -m mospolytech_mcp.server --http --host $(HOST) --port $(PORT)

test: install ## офлайн-тесты
	$(PY) -m pytest -q

check-lk: install .env ## проверка lk_api на реальном аккаунте
	$(PY) scripts/check_lk_api.py

docker-up: 
	docker compose up --build -d

docker-down: 
	docker compose down

docker-logs: 
	docker compose logs -f

clean: ## удалить .venv и кэши
	$(SYS_PYTHON) -c "import shutil; [shutil.rmtree(p, ignore_errors=True) for p in ('.venv', '.pytest_cache')]"
