# Development Guide

This guide covers setting up a local development environment for Sentinel.

## Prerequisites

### Required

- **Python 3.11+** - For Python services
- **Go 1.21+** - For Node Agent
- **Docker & Docker Compose** - For local infrastructure
- **kubectl** - Kubernetes CLI
- **kind** or **minikube** - Local Kubernetes cluster
- **Helm 3.x** - Kubernetes package manager

### Optional

- **pre-commit** - Git hooks for code quality
- **golangci-lint** - Go linter
- **k9s** - Kubernetes TUI

## Initial Setup

### 1. Clone the Repository

```bash
git clone https://github.com/<org>/sentinel.git
cd sentinel
```

### 2. Install Development Tools

```bash
make install-dev
```

This installs:
- Python linting and formatting tools (black, ruff, mypy)
- Go linting tools (golangci-lint)
- Pre-commit hooks

### 3. Start Local Infrastructure

```bash
make dev-up
```

This starts:
- Prometheus (http://localhost:9090)
- Grafana (http://localhost:3000)
- Kafka + UI (http://localhost:8080)
- Vault (http://localhost:8200)

### 4. Create Local Kubernetes Cluster

```bash
# Using kind
kind create cluster --name sentinel-dev --config deploy/kind-config.yaml

# OR using minikube
minikube start --profile sentinel-dev
```

## Service Development

### Control API (Python/FastAPI)

```bash
cd services/control-api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -e ".[dev]"

# Run locally
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v --cov=app

# Format and lint
black .
ruff check .
mypy app/
```

### Node Agent (Go)

```bash
cd services/agent

# Download dependencies
go mod download

# Run locally
go run cmd/agent/main.go --config ../../deploy/config/agent-local.yaml

# Run tests
go test ./... -v -cover

# Format and lint
go fmt ./...
golangci-lint run

# Build binary
go build -o bin/sentinel-agent cmd/agent/main.go
```

### Pipeline Controller (Python)

```bash
cd services/pipeline-controller

python -m venv venv
source venv/bin/activate

pip install -e ".[dev]"

python -m app.main

pytest tests/ -v
```

### InfraMind Adapter (Python)

```bash
cd services/infra-adapter

python -m venv venv
source venv/bin/activate

pip install -e ".[dev]"

# Generate protobuf code first
cd ../../proto
python -m grpc_tools.protoc -I. \
  --python_out=../services/infra-adapter/app \
  --grpc_python_out=../services/infra-adapter/app \
  sentinel.proto

cd ../services/infra-adapter
python -m app.main

pytest tests/ -v
```

## Testing

### Unit Tests

```bash
# Test all services
make test-unit

# Test specific service
make test-control-api
make test-agent
```

### Integration Tests

```bash
# Start local environment first
make dev-up

# Run integration tests
make test-integration
```

### Chaos Tests

```bash
make test-chaos
```

## Code Quality

### Formatting

```bash
# Format all code
make format

# Format Python only
make format-python

# Format Go only
make format-go
```

### Linting

```bash
# Lint all code
make lint

# Lint Python only
make lint-python

# Lint Go only
make lint-go
```

### Pre-commit Hooks

```bash
# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

## Building

### Build All Services

```bash
make build
```

### Build Docker Images

```bash
make docker-build
```

### Build Specific Service

```bash
# Python service
cd services/control-api
pip install -e .

# Go agent
cd services/agent
go build -o bin/sentinel-agent cmd/agent/main.go
```

## Debugging

### Python Services

Use built-in debugger or IDE debugging:

```python
# Add breakpoint in code
breakpoint()

# Or use VS Code launch.json
```

### Go Agent

```bash
# Run with delve debugger
dlv debug cmd/agent/main.go -- --config config.yaml
```

### Kubernetes Issues

```bash
# Check pod logs
kubectl logs -n sentinel-system <pod-name>

# Get pod status
kubectl describe pod -n sentinel-system <pod-name>

# Port forward to service
kubectl port-forward -n sentinel-system svc/sentinel-api 8000:8000
```

## Protobuf Development

When modifying `.proto` files:

```bash
# Generate Python code
make proto-gen

# Or manually
cd proto
python -m grpc_tools.protoc -I. \
  --python_out=../services/infra-adapter/app \
  --grpc_python_out=../services/infra-adapter/app \
  sentinel.proto
```

## Common Tasks

### Reset Local Environment

```bash
make dev-down
make clean
make dev-up
```

### View Logs

```bash
# Docker Compose logs
make dev-logs

# Specific service
cd deploy/docker-compose
docker compose logs -f prometheus
```

### Deploy to Local K8s

```bash
# Build images
make docker-build

# Load images into kind
kind load docker-image ghcr.io/sentinel/sentinel-api:0.1.0 --name sentinel-dev

# Deploy with Helm
make k8s-deploy
```

## Troubleshooting

### Python Import Errors

```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall in editable mode
pip install -e .
```

### Go Module Issues

```bash
# Clean module cache
go clean -modcache

# Re-download dependencies
go mod download
```

### Docker Issues

```bash
# Clean Docker system
docker system prune -a

# Restart Docker Desktop
```

### Kubernetes Issues

```bash
# Delete and recreate cluster
kind delete cluster --name sentinel-dev
kind create cluster --name sentinel-dev
```

## Next Steps

- Read the [Architecture Guide](../architecture/README.md)
- Review the [API Reference](../api/openapi.yaml)
- Check out the [Operator Runbook](../runbooks/operator-guide.md)
