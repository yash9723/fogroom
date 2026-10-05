# FOGROOM developer commands (Unix/macOS/WSL).
# Windows PowerShell equivalent: scripts/dev.ps1 <target>  (e.g. ./scripts/dev.ps1 setup)

API_DIR := apps/api
ifeq ($(OS),Windows_NT)
  PY := $(API_DIR)/.venv/Scripts/python
else
  PY := $(API_DIR)/.venv/bin/python
endif

.PHONY: setup dev dev-api dev-web test test-api test-web e2e lint seed migrate reset-db docker-up docker-down

setup:
	@test -f .env || cp .env.example .env
	python -m venv $(API_DIR)/.venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -e "$(API_DIR)[dev]"
	pnpm install
	docker compose up -d postgres redis
	$(MAKE) migrate
	$(MAKE) seed

migrate:
	cd $(API_DIR) && ../../$(PY) -m alembic upgrade head

seed:
	cd $(API_DIR) && ../../$(PY) -m app.seed

reset-db:
	cd $(API_DIR) && ../../$(PY) -m alembic downgrade base && ../../$(PY) -m alembic upgrade head && ../../$(PY) -m app.seed

dev-api:
	cd $(API_DIR) && ../../$(PY) -m uvicorn app.main:app --reload --port 8000

dev-web:
	pnpm --filter @fogroom/web dev

dev:
	docker compose up -d postgres redis
	$(MAKE) -j2 dev-api dev-web

test-api:
	cd $(API_DIR) && ../../$(PY) -m pytest -q

test-web:
	pnpm --filter @fogroom/web test

test: test-api test-web

e2e:
	pnpm --filter @fogroom/web e2e

lint:
	cd $(API_DIR) && ../../$(PY) -m ruff check . && ../../$(PY) -m ruff format --check . && ../../$(PY) -m mypy app
	pnpm --filter @fogroom/web lint
	pnpm --filter @fogroom/web typecheck

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
