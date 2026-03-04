.PHONY: help install dev test lint typecheck check up down migrate

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -e .

dev: ## Install dev dependencies
	pip install -e ".[dev]"

test: ## Run all tests
	python -m pytest tests/ -v

lint: ## Run linter
	ruff check src/ tests/

typecheck: ## Run type checker
	mypy src/

check: lint typecheck test ## Run all checks (lint + typecheck + test)

up: ## Start all services
	docker compose up -d

down: ## Stop all services
	docker compose down

migrate: ## Run database migrations
	alembic upgrade head
