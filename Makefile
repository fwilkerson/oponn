.PHONY: help run test lint format typecheck
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Run in development mode (permissive, hot-reload)
	poetry run ./dev.py dev

prod: ## Run in production mode (Gunicorn, strict dependencies)
	poetry run ./dev.py prod

services-up: ## Start Postgres and Redis
	poetry run ./dev.py services start

services-down: ## Stop Postgres and Redis
	poetry run ./dev.py services stop

migrate: ## Generate new DB migration
	poetry run ./dev.py migrate

upgrade: ## Apply DB migrations
	poetry run ./dev.py upgrade

test: ## Run test
	unset DATABASE_URL && poetry run ./dev.py test --ignore=tests/test_sql_repo.py

test-sql: ## Run PostgreSQL integration tests
	poetry run ./dev.py test tests/test_sql_repo.py

lint: ## Automatically fix linting issues with Ruff
	poetry run ./dev.py lint

lint-ui: ## Check HTML/CSS/JS with djlint
	poetry run ./dev.py lint-ui

format: ## Automatically format files with Ruff
	poetry run ./dev.py format

format-ui: ## Automatically format HTML/CSS/JS with djlint
	poetry run ./dev.py format-ui

typecheck: ## Check types with basedpyright
	poetry run ./dev.py typecheck
