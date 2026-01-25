.PHONY: help run test lint format typecheck
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

start: ## Run the FastAPI application
	poetry run ./dev.py start

test: ## Run tests (use poetry run ./dev.py test [args] for more flexibility)
	poetry run ./dev.py test

lint: ## Automatically fix linting issues with Ruff
	poetry run ./dev.py lint

format: ## Automatically format files with Ruff
	poetry run ./dev.py format

typecheck: ## Check types with basedpyright
	poetry run ./dev.py typecheck
