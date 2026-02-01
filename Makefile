.PHONY: help dev prod services-up services-down services-purge migrate upgrade test lint check keyset simulate
.DEFAULT_GOAL := help

# Helper to run the CLI tool
CLI := poetry run python manage.py

help: ## Display this help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
prod: ## Start production server
	$(CLI) prod

services-up: ## Start infrastructure
	$(CLI) infra up

services-down: ## Stop infrastructure
	$(CLI) infra down

services-purge: ## Wipe DB and Redis
	$(CLI) infra purge

migrate: ## Generate migration (e.g. make migrate MSG="add users")
	$(CLI) db migrate --message "$(MSG)"

upgrade: ## Apply migrations
	$(CLI) db upgrade

keyset: ## Generate master key
	$(CLI) keyset

simulate: ## Simulate votes: make simulate ID=ballot_id VOTES=10
	$(CLI) simulate $(ID) --votes $(VOTES)

test: ## Run tests (args via ARGS="...")
	$(CLI) test $(ARGS)

lint: ## Lint and format
	$(CLI) lint

check: ## Full QA suite
	$(CLI) check
