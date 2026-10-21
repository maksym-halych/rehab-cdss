.DEFAULT_GOAL := help
.PHONY: help pre-commit api frontend

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

pre-commit: ## Run pre-commit hooks on all files
	uv run --project api pre-commit run --all-files

api: ## Start the API on :8000 (docs on /api/docs)
	cd api && uv run --env-file .env rehab-api

frontend: ## Start the frontend on :3000
	cd frontend && npm run dev
