PYTHON ?= python
COMPOSE = docker compose -f deploy/compose/docker-compose.yml

.PHONY: install lint format typecheck test check run-gateway run-worker up down

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

typecheck:
	$(PYTHON) -m mypy

test:
	$(PYTHON) -m pytest

check: lint typecheck test

run-gateway:
	$(PYTHON) -m inferscale.gateway

run-worker:
	$(PYTHON) -m inferscale.worker

up:
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down
