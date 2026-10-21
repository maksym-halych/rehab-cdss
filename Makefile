.DEFAULT_GOAL := help
.PHONY: help pre-commit test docker-check api frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

pre-commit: ## Run pre-commit hooks on all files
	uv run --project api pre-commit run --all-files

test: ## Run offline backend tests and save coverage reports
	cd api && uv run --locked pytest --cov --cov-fail-under=60 --cov-report=term-missing --cov-report=xml:coverage.xml --cov-report=html:htmlcov

docker-check: ## Build the API image without deploying it
	docker build --progress=plain --tag rehab-cdss:ci ./api

api: ## Start the API on :8000 (docs on /api/docs)
	cd api && uv run --env-file .env rehab-api

frontend: ## Start the frontend on :3000
	cd frontend && npm run dev
