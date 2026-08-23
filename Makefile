.PHONY: help test test-unit test-contract test-integration test-resilience lint verify-manifests compose-up compose-down

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

test: test-unit test-contract test-integration test-resilience ## Run all test suites

test-unit: ## Run unit tests
	python -m pytest services/tracking-worker/tests -v

test-contract: ## Run contract schema tests
	python -m pytest tests/contract -v

test-integration: ## Run integration tests
	python -m pytest tests/integration -v

test-resilience: ## Run chaos and resilience drill tests
	python -m pytest tests/resilience -v

lint: ## Run code linters (ruff, mypy)
	python -m ruff check services/tracking-worker tests scripts
	python -m ruff format --check services/tracking-worker tests scripts
	python -m mypy services/tracking-worker/src

verify-manifests: ## Validate Kubernetes and Policy manifest schemas
	python scripts/verify_manifests.py

compose-up: ## Start local docker-compose environment
	docker compose -f deploy/compose/docker-compose.yml up --build -d

compose-down: ## Stop local docker-compose environment
	docker compose -f deploy/compose/docker-compose.yml down -v
