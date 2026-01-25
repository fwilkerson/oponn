.PHONY: help run test lint lint-fix check-types
.DEFAULT_GOAL := help

help:
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "[36m%-20s[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

start: ## Run the FastAPI application
	poetry run uvicorn src.main:app --reload

test: ## Run tests
	poetry run python -m pytest tests/

lint: ## Automatically fix linting issues with Ruff
	poetry run python -m ruff check src/ tests/ --fix

format: ## Automatically format files with Ruff
	poetry run python -m ruff format src/ tests/

typecheck: ## Check types with basedpyright
	poetry run basedpyright src/
