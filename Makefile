.DEFAULT_GOAL := help
CORE := apps/core

.PHONY: help setup lint format types test check

help: ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup: ## Install core dependencies
	cd $(CORE) && uv sync

lint: ## Ruff lint + format check
	cd $(CORE) && uv run ruff check . && uv run ruff format --check .

format: ## Auto-format
	cd $(CORE) && uv run ruff check --fix . && uv run ruff format .

types: ## Strict type check
	cd $(CORE) && uv run mypy

test: ## Run tests
	cd $(CORE) && uv run pytest

check: lint types test ## Everything CI runs for the core
