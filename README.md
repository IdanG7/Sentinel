# Sentinel

> **Autonomous AI Infrastructure Platform powered by InfraMind**

[![Phase](https://img.shields.io/badge/Phase-5%20Complete-success?style=flat-square)](ROADMAP.md)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Go](https://img.shields.io/badge/Go-1.21+-00ADD8?style=flat-square&logo=go&logoColor=white)](https://golang.org/)

Sentinel is a production-ready autonomous infrastructure controller for AI/ML workloads. It provides predictive scaling, intelligent scheduling, and self-healing capabilities across Kubernetes clusters and edge nodes.

## Overview

Sentinel integrates with **InfraMind** (the predictive brain) to form a closed feedback loop:

```
Observe → Predict → Act → Learn
```

- **Observe:** Collect telemetry from clusters, nodes, and workloads
- **Predict:** InfraMind analyzes patterns and generates optimization plans
- **Act:** Sentinel executes changes with policy enforcement and safety guardrails
- **Learn:** Feed results back to InfraMind for continuous improvement

## Key Features

### 🤖 **Phase 5: Intelligent Agent Orchestration** ✅ NEW
- **Agent Controller** - Autonomous AI agent orchestration with task queue and registry
- **PatchBot** - Auto-fixes CI/CD failures (linting, formatting, tests) and creates PRs
- **Failure Ingestion** - GitHub/GitLab webhook receivers with automatic failure classification
- **Agent SDK** - Standard interface for building autonomous remediation agents
- **Smart Rate Limiting** - Confidence thresholds, blast radius control, and cooldown periods
- **InfraMind Integration** - Prediction-to-outcome correlation for continuous learning

### 🔒 **Phase 4: Production Hardening** ✅
- **mTLS encryption** - Mutual TLS for all inter-service communication with cert-manager
- **HashiCorp Vault** - Zero-trust secrets management with dynamic credentials
- **RBAC enforcement** - Role-based access control (Viewer, Operator, Admin, System)
- **Chaos testing** - Pod failures, network partitions, resource stress tests
- **Load testing** - Comprehensive performance validation with Locust
- **Operational runbooks** - Incident response and troubleshooting guides

### 🚀 **Phase 3: Production-Ready Safety & Rollouts**
- **Canary deployments** with progressive traffic shifting and health gates
- **Shadow evaluation mode** - Test plans safely without execution
- **Change freeze windows** - Timezone-aware deployment blocking (weekends, holidays)
- **Rate limiting** - Sliding window algorithm with per-resource tracking
- **Automated rollbacks** - Health monitoring with auto-trigger on failures
- **Health scoring** - Multi-criteria deployment health (0.0-1.0)

### 🏗️ **Core Platform**
- **Multi-cluster orchestration** (cloud + on-prem + edge)
- **Predictive autoscaling** guided by ML models (InfraMind integration)
- **Policy-driven automation** (SLA, SLO, cost, quota, freeze, rate limit enforcement)
- **GPU-aware scheduling** with heterogeneous hardware support
- **Comprehensive observability** (Prometheus, Grafana, Kafka events)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       InfraMind (Brain)                      │
│  Telemetry Ingestor → Models → Optimization → Decision API  │
└────────────────────────────┬────────────────────────────────┘
                             │
                   ┌─────────▼─────────┐
                   │   Action Plans    │
                   └─────────┬─────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│                    Sentinel (Executor)                       │
│                                                              │
│  Control API → Policy Engine → Pipeline Controller          │
│       │                              │                       │
│       └──────────┐          ┌────────┴───────┐             │
│                  │          │                │             │
│            K8s Driver    Node Agents   Telemetry Plane     │
└──────────────────────────────────────────────────────────────┘
```

## Repository Structure

```
sentinel/
├── services/              # Microservices
│   ├── control-api/       # REST API (FastAPI)
│   ├── pipeline-controller/   # Orchestration engine
│   ├── infra-adapter/     # InfraMind integration
│   └── agent/             # Node agent (Go)
├── libs/                  # Shared libraries
│   ├── policy-engine/     # Policy evaluation
│   ├── k8s-driver/        # Kubernetes abstraction
│   └── sentinel-common/   # Common utilities
├── charts/                # Helm charts
├── deploy/                # Deployment configs
├── proto/                 # gRPC definitions
├── sdk/                   # Python SDK for operators
├── docs/                  # Documentation
├── scripts/               # Build & dev scripts
└── tests/                 # Integration & chaos tests
```

## Quick Start

### Prerequisites

- **Docker & Docker Compose** - For local development environment
- **Python 3.11+** - For API services
- **Go 1.21+** - For node agent
- **kubectl & Helm 3.x** - For Kubernetes deployment (optional)

### Local Development

**1. Start the observability stack:**

```bash
# Start Prometheus, Grafana, Kafka, PostgreSQL, etc.
make dev-up

# Verify services are running
docker compose -f deploy/docker-compose/docker-compose.yml ps
```

**2. Run the Control API:**

```bash
cd services/control-api
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

**3. Run the Node Agent:**

```bash
cd services/agent
go run cmd/agent/main.go --config config.example.yaml
```

**4. Access the services:**

| Service | URL | Credentials |
|---------|-----|-------------|
| Control API (Swagger) | http://localhost:8000/docs | admin / secret |
| Prometheus | http://localhost:9090 | - |
| Grafana | http://localhost:3000 | admin / sentinel |
| Kafka UI | http://localhost:8080 | - |
| Agent Metrics | http://localhost:9100/metrics | - |

**5. Test the API:**

```bash
# Get JWT token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"secret"}'

# Use token to access API
export TOKEN="<your_access_token>"
curl http://localhost:8000/api/v1/workloads \
  -H "Authorization: Bearer $TOKEN"
```

### Deploy to Kubernetes

```bash
# Install from local charts
helm install sentinel charts/sentinel-core \
  --namespace sentinel-system \
  --create-namespace

# Install node agent
helm install sentinel-agent charts/sentinel-agent \
  --namespace sentinel-system

# Verify deployment
kubectl get pods -n sentinel-system
```

See [charts/README.md](charts/README.md) for detailed Helm chart documentation.

## Development

### Services

Each service has its own README with specific setup instructions:

- [Control API](services/control-api/README.md) - REST API for deployments, policies, actions
- [Pipeline Controller](services/pipeline-controller/README.md) - Orchestration & reconciliation
- [InfraMind Adapter](services/infra-adapter/README.md) - gRPC bridge to InfraMind
- [Node Agent](services/agent/README.md) - Metrics collection & local execution

### Conventions

- **Naming:** kebab-case for resources, snake_case in JSON, lowerCamelCase in proto
- **Labels:** `app=sentinel`, `component=<name>`, `tenant=<id>`
- **Commit messages:** Conventional Commits format
- **Testing:** Unit tests required for all PRs; integration tests for critical paths

## Documentation

- [Architecture Guide](docs/architecture/README.md) - System architecture with Mermaid diagrams
- [Development Guide](docs/guides/development.md) - Local development setup
- [Docker Compose Guide](deploy/docker-compose/README.md) - Local environment setup
- [API Documentation](http://localhost:8000/docs) - Interactive API docs (when running locally)

## Observability

### Dashboards

- **SRE Overview:** Error budgets, alerts, action plan throughput
- **GPU Fleet:** Utilization, PCIe saturation, throttling
- **Workload Health:** Latency percentiles, queue depth, success rate
- **Deployments:** Rollout progress, canary metrics, rollback frequency

### Key Metrics

```promql
sentinel_controller_reconciliations_total{result="success"}
sentinel_policy_violations_total{type="cost_ceiling"}
workload_inference_latency_ms{model="embeddings",p="95"}
gpu_utilization_percent{node="gpu-node-01",sku="L4"}
```

## Security

- **Authentication:** JWT for users, mTLS for inter-service
- **Authorization:** RBAC (viewer, operator, admin, system roles)
- **Secrets:** HashiCorp Vault integration
- **Supply Chain:** Signed images (Cosign), SBOM generation
- **Audit:** Immutable append-only logs

## Distribution & Deployment

### Docker Images

Built and published via GitHub Actions:
- `ghcr.io/sentinel/sentinel-control-api`
- `ghcr.io/sentinel/sentinel-pipeline-controller`
- `ghcr.io/sentinel/sentinel-infra-adapter`
- `ghcr.io/sentinel/sentinel-agent`

All images are:
- ✅ Multi-platform (amd64/arm64)
- ✅ Signed with Cosign
- ✅ Scanned for vulnerabilities
- ✅ Include SBOM attestations

### Helm Charts

Available in the `charts/` directory:
- `sentinel-core` - Control plane services
- `sentinel-agent` - Node monitoring agent

### Agent Binaries

Pre-built binaries available for:
- Linux (amd64, arm64)
- macOS (amd64, arm64/Apple Silicon)
- Windows (amd64)

Download from [GitHub Releases](../../releases).

## Roadmap

See [ROADMAP.md](ROADMAP.md) for detailed phases and milestones.

- [x] **Phase 0: Scaffolding** ✅ Complete
  - Repository structure, CI/CD, dev environment
  - Control API with JWT auth
  - Node Agent with metrics exporter
  - Helm charts, SBOM & image signing
- [x] **Phase 1: Orchestration + Observability** ✅ Complete
  - Kubernetes driver with watch & reconciliation
  - Policy engine with 5 rule types (cost, quota, SLA, SLO, rate limit)
  - Database integration (PostgreSQL)
  - Observability stack (Prometheus + Grafana dashboards)
  - Event-driven architecture (Kafka)
  - 40+ tests with 94% coverage
- [x] **Phase 2: InfraMind Integration** ✅ Complete
  - gRPC telemetry streaming to InfraMind
  - Action plan execution pipeline
  - Closed feedback loop operational
- [x] **Phase 3: Safety, Rollouts, Canary** ✅ Complete
  - Canary deployments with progressive rollout
  - Automated rollbacks on health check failure
  - Shadow evaluation mode
  - Rate limiting and change freeze windows
- [x] **Phase 4: Production Hardening** ✅ Complete
  - mTLS with cert-manager (90-day rotation)
  - HashiCorp Vault integration
  - RBAC with 4 roles and 20+ permissions
  - Chaos testing suite (pod failures, network partition, resource stress)
  - Load testing with Locust
  - Operational runbooks and documentation
- [x] **Phase 5: Agent Orchestration (PatchBot)** ✅ Complete
  - Agent Controller service with task queue
  - PatchBot agent for automatic CI/CD failure fixes
  - Failure Ingestion service with GitHub/GitLab webhooks
  - Agent SDK for building autonomous agents
  - Rate limiting and policy enforcement
- [ ] **Phase 6: Multi-Tenancy & Federation** (Next)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow, PR guidelines, and coding standards.

## License

[Apache 2.0](LICENSE)

## Getting Help

- 📖 **Documentation:** [Architecture Guide](docs/architecture/README.md) | [Development Guide](docs/guides/development.md)
- 🐛 **Bug Reports:** [GitHub Issues](../../issues)
- 💬 **Discussions:** [GitHub Discussions](../../discussions)
- 🚀 **Feature Requests:** [GitHub Issues](../../issues/new?template=feature_request.md)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development workflow and setup
- Code style and conventions
- Pull request process
- Testing requirements

---

<div align="center">

**Status:** Phase 5 Complete ✅ | AI-Driven Agent Orchestration with PatchBot

**Built with**

Python • Go • FastAPI • Kubernetes • Prometheus • Kafka • PostgreSQL

[Architecture](docs/architecture/README.md) • [Roadmap](ROADMAP.md) • [Testing](TESTING.md) • [Contributing](CONTRIBUTING.md) • [License](LICENSE)

</div>
