.PHONY: help dev-up dev-down test test-unit test-integration lint format clean build docker-build

# Default target
.DEFAULT_GOAL := help

# Variables
DOCKER_REGISTRY ?= ghcr.io
ORG ?= sentinel
VERSION ?= 0.1.0
PYTHON_SERVICES = control-api pipeline-controller infra-adapter
GO_SERVICES = agent

help: ## Show this help message
	@echo "Sentinel - Autonomous AI Infrastructure Platform"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# Development Environment
dev-up: ## Start local development environment
	@echo "Starting development environment..."
	cd deploy/docker-compose && docker compose up -d
	@echo "Services available:"
	@echo "  - Control API: http://localhost:8000"
	@echo "  - Prometheus: http://localhost:9090"
	@echo "  - Grafana: http://localhost:3000"
	@echo "  - Kafka UI: http://localhost:8080"

dev-down: ## Stop local development environment
	@echo "Stopping development environment..."
	cd deploy/docker-compose && docker compose down

dev-logs: ## Show logs from dev environment
	cd deploy/docker-compose && docker compose logs -f

# Testing
test: test-unit test-integration ## Run all tests

test-unit: ## Run unit tests
	@echo "Running unit tests..."
	@for service in $(PYTHON_SERVICES); do \
		echo "Testing services/$$service..."; \
		cd services/$$service && python -m pytest tests/ -v --cov=app || exit 1; \
		cd ../..; \
	done
	@echo "Testing Go agent..."
	cd services/agent && go test ./... -v -cover

test-integration: ## Run integration tests
	@echo "Running integration tests..."
	cd tests/integration && python -m pytest -v

test-chaos: ## Run chaos tests
	@echo "Running chaos tests..."
	cd tests/chaos && python -m pytest -v

test-control-api: ## Test control-api service
	cd services/control-api && python -m pytest tests/ -v --cov=app

test-agent: ## Test agent service
	cd services/agent && go test ./... -v -cover

# Linting & Formatting
lint: lint-python lint-go ## Run all linters

lint-python: ## Lint Python code
	@echo "Linting Python code..."
	@for service in $(PYTHON_SERVICES); do \
		echo "Linting services/$$service..."; \
		cd services/$$service && ruff check . && mypy app/ || exit 1; \
		cd ../..; \
	done

lint-go: ## Lint Go code
	@echo "Linting Go code..."
	cd services/agent && go vet ./... && golangci-lint run

format: format-python format-go ## Format all code

format-python: ## Format Python code
	@echo "Formatting Python code..."
	@for service in $(PYTHON_SERVICES); do \
		echo "Formatting services/$$service..."; \
		cd services/$$service && black . && ruff check --fix . || true; \
		cd ../..; \
	done

format-go: ## Format Go code
	@echo "Formatting Go code..."
	cd services/agent && go fmt ./... && goimports -w .

# Building
build: build-python build-go ## Build all services

build-python: ## Build Python services
	@echo "Building Python services..."
	@for service in $(PYTHON_SERVICES); do \
		echo "Building services/$$service..."; \
		cd services/$$service && pip install -e . || exit 1; \
		cd ../..; \
	done

build-go: ## Build Go services
	@echo "Building Go agent..."
	cd services/agent && go build -o bin/sentinel-agent cmd/agent/main.go

# Docker
docker-build: ## Build Docker images
	@echo "Building Docker images..."
	docker build -t $(DOCKER_REGISTRY)/$(ORG)/sentinel-control-api:$(VERSION) -f services/control-api/Dockerfile services/control-api
	docker build -t $(DOCKER_REGISTRY)/$(ORG)/sentinel-pipeline-controller:$(VERSION) -f services/pipeline-controller/Dockerfile services/pipeline-controller
	docker build -t $(DOCKER_REGISTRY)/$(ORG)/sentinel-infra-adapter:$(VERSION) -f services/infra-adapter/Dockerfile services/infra-adapter
	docker build -t $(DOCKER_REGISTRY)/$(ORG)/sentinel-agent:$(VERSION) -f services/agent/Dockerfile services/agent

docker-push: docker-build ## Push Docker images
	@echo "Pushing Docker images..."
	docker push $(DOCKER_REGISTRY)/$(ORG)/sentinel-control-api:$(VERSION)
	docker push $(DOCKER_REGISTRY)/$(ORG)/sentinel-pipeline-controller:$(VERSION)
	docker push $(DOCKER_REGISTRY)/$(ORG)/sentinel-infra-adapter:$(VERSION)
	docker push $(DOCKER_REGISTRY)/$(ORG)/sentinel-agent:$(VERSION)

# Protobuf
proto-gen: ## Generate protobuf code
	@echo "Generating protobuf code..."
	cd proto && python -m grpc_tools.protoc -I. --python_out=../services/infra-adapter/app --grpc_python_out=../services/infra-adapter/app sentinel.proto

# Kubernetes
k8s-deploy: ## Deploy to local Kubernetes
	@echo "Deploying to Kubernetes..."
	helm upgrade --install sentinel charts/sentinel-core --namespace sentinel-system --create-namespace

k8s-uninstall: ## Uninstall from Kubernetes
	@echo "Uninstalling from Kubernetes..."
	helm uninstall sentinel --namespace sentinel-system

# Clean
clean: ## Clean build artifacts
	@echo "Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	cd services/agent && rm -rf bin/ || true

# Documentation
docs-serve: ## Serve documentation locally
	@echo "Serving documentation..."
	cd docs && python -m http.server 8001

# Install development dependencies
install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	pip install pre-commit black ruff mypy pytest pytest-cov
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	pre-commit install
