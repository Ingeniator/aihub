.DEFAULT_GOAL := help

COMPOSE := docker compose

CYAN  := \033[36m
RESET := \033[0m

.PHONY: help
help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "$(CYAN)%-15s$(RESET) %s\n", $$1, $$2}'

## ---------- Development ----------

.PHONY: dev
dev:  ## Run dev server with auto-reload (local)
	uv run uvicorn aihub.main:app --reload --port 5000

.PHONY: test
test:  ## Run tests locally
	uv run pytest tests/ -v

.PHONY: lint
lint:  ## Lint source and tests
	uv run ruff check src/ tests/

## ---------- Docker ----------

.PHONY: build
build:  ## Build all Docker images
	$(COMPOSE) build

.PHONY: up
up:  ## Start postgres + aihub
	$(COMPOSE) up -d --build

.PHONY: down
down:  ## Stop and remove containers
	$(COMPOSE) down

.PHONY: down-v
down-v:  ## Stop and remove containers + volumes
	$(COMPOSE) down -v

.PHONY: test-docker
test-docker:  ## Run tests in an isolated Docker container
	$(COMPOSE) --profile test run --rm test

.PHONY: seed
seed:  ## Seed local database with sample data
	uv run python scripts/seed.py

.PHONY: seed-reset
seed-reset:  ## Truncate and re-seed local database
	uv run python scripts/seed.py --reset

.PHONY: seed-docker
seed-docker:  ## Re-run seeder via Docker (skips existing data)
	$(COMPOSE) run --rm seed

.PHONY: seed-docker-reset
seed-docker-reset:  ## Truncate and re-seed via Docker
	$(COMPOSE) run --rm seed --reset

.PHONY: logs
logs:  ## Follow aihub logs
	$(COMPOSE) logs -f aihub

.PHONY: ps
ps:  ## Show running services
	$(COMPOSE) ps
