# QuantForg — Development & Operations Makefile
# Usage: make <target>

.DEFAULT_GOAL := help
.PHONY: help install install-dev sync lock lint format typecheck test test-unit \
	test-integration coverage run run-prod migrate migrate-create migrate-down \
	docker-up docker-down docker-build docker-logs docker-shell clean pre-commit \
	ci security check

PYTHON ?= python3.13
POETRY ?= poetry
COMPOSE ?= docker compose
COMPOSE_FILE ?= docker-compose.yml

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

install: ## Install production dependencies
	$(POETRY) install --only main

install-dev: ## Install all dependencies including dev tools
	$(POETRY) install

sync: ## Sync lockfile and install
	$(POETRY) lock
	$(POETRY) install

lock: ## Update poetry.lock without installing
	$(POETRY) lock --no-update

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint: ## Run Ruff linter
	$(POETRY) run ruff check app core tests

format: ## Format code with Black and Ruff
	$(POETRY) run black app core tests
	$(POETRY) run ruff check --fix app core tests

typecheck: ## Run MyPy strict type checking
	$(POETRY) run mypy app core

pre-commit: ## Run all pre-commit hooks
	$(POETRY) run pre-commit run --all-files

security: ## Run security-focused Ruff rules
	$(POETRY) run ruff check --select S app core

check: lint typecheck test ## Run full local quality gate

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

test: ## Run full test suite
	$(POETRY) run pytest

test-unit: ## Run unit tests only
	$(POETRY) run pytest -m unit

test-integration: ## Run integration tests only
	$(POETRY) run pytest -m integration

coverage: ## Generate HTML coverage report
	$(POETRY) run pytest --cov-report=html
	@echo "Coverage report: htmlcov/index.html"

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

run: ## Start development server with hot reload
	$(POETRY) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

run-prod: ## Start production server
	$(POETRY) run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

migrate: ## Apply all pending Alembic migrations
	$(POETRY) run alembic upgrade head

migrate-create: ## Create a new migration (usage: make migrate-create msg="description")
	$(POETRY) run alembic revision --autogenerate -m "$(msg)"

migrate-down: ## Roll back one migration
	$(POETRY) run alembic downgrade -1

migrate-history: ## Show migration history
	$(POETRY) run alembic history --verbose

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------

docker-up: ## Start all Docker services
	$(COMPOSE) -f $(COMPOSE_FILE) up -d

docker-down: ## Stop all Docker services
	$(COMPOSE) -f $(COMPOSE_FILE) down

docker-build: ## Build Docker images
	$(COMPOSE) -f $(COMPOSE_FILE) build

docker-logs: ## Tail Docker service logs
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f

docker-shell: ## Open a shell in the API container
	$(COMPOSE) -f $(COMPOSE_FILE) exec api /bin/bash

docker-ps: ## List running containers
	$(COMPOSE) -f $(COMPOSE_FILE) ps

# ---------------------------------------------------------------------------
# CI
# ---------------------------------------------------------------------------

ci: ## Run CI pipeline locally (lint + typecheck + test)
	$(POETRY) run ruff check app core tests
	$(POETRY) run black --check app core tests
	$(POETRY) run mypy app core
	$(POETRY) run pytest

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Remove caches, build artifacts, and coverage data
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	rm -rf dist build .tox
