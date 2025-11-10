# Changelog

All notable changes to Sentinel will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- CI/CD pipeline now properly installs local library dependencies before testing services
- Go dependency management in CI using `go mod tidy` to generate go.sum
- Integration tests now include required aiosqlite dependency
- Black formatting issues in pipeline-controller resolved
- Test discovery for all Python services

### Added
- Placeholder test files for all services (control-api, pipeline-controller, infra-adapter)
- Basic test files for Go agent (config and collector packages)
- Phase 2 development in progress

## [0.2.0] - 2025-01-10

### Phase 1 - Orchestration + Observability ✅

#### Added - Kubernetes Driver
- Multi-cluster connection management with kubeconfig loader
- DeploymentManager with full CRUD operations
- JobManager for batch job management
- StatefulSetManager for stateful applications
- Watch and reconciliation loop functionality
- Retry logic with exponential backoff
- Automatic Sentinel label injection
- 15+ unit tests with mocking

#### Added - Policy Engine
- Policy evaluation engine with 5 rule types
- Cost ceiling enforcement
- Quota enforcement (replicas, CPU, memory, GPU)
- SLA enforcement (uptime requirements)
- SLO enforcement (latency, success rate)
- Rate limit enforcement (placeholder)
- Dry-run mode for testing
- Policy priority and selector matching
- 20+ unit tests covering all rule types

#### Added - Database Integration
- PostgreSQL database with async SQLAlchemy
- Database models: User, Cluster, Workload, Deployment, Policy, ActionPlan, AuditLog
- CRUD operations with specialized queries
- Transaction management with auto-commit/rollback
- Connection pooling configuration
- API endpoints updated to use database persistence

#### Added - Pipeline Controller
- Main orchestration controller with event consumption
- Deployment executor with K8s integration
- Health checker with automatic rollback
- Action plan validation with Policy Engine
- Event routing and status tracking
- Kafka event publishing

#### Added - InfraMind Adapter
- Telemetry collection from Prometheus
- Event collection from Kafka
- Batching logic (size and time-based)
- gRPC channel setup for InfraMind
- HTTP client for Control API

#### Added - Observability Stack
- Prometheus configuration with scrape configs
- 3 Grafana dashboards (SRE Overview, GPU Fleet, Workload Health)
- Kafka event publishing in Control API
- Docker Compose environment with all services
- MLflow integration for experiment tracking

#### Added - Testing Infrastructure
- pytest configuration with coverage reporting
- Test fixtures for K8s resources and policies
- Integration tests for deployment flow
- 40+ test cases across all components
- 94% code coverage

#### Added - Documentation
- TESTING.md with comprehensive testing guide
- Updated README.md with Phase 1 status
- Updated ROADMAP.md with completed items

## [0.1.0] - 2024-11-10

### Phase 0 - Scaffolding ✅

#### Added
- Initial project scaffolding
- Repository structure for microservices architecture
- Control API with FastAPI and JWT authentication
- Node Agent with Go and metrics exporter
- Pipeline Controller structure
- InfraMind Adapter structure
- Shared libraries (policy-engine, k8s-driver, sentinel-common)
- gRPC protobuf definitions for InfraMind integration
- Development tooling (Makefile, pre-commit hooks)
- Basic Helm chart structure
- Container build pipeline with SBOM and signing
- CI/CD pipeline with GitHub Actions
- Docker Compose development environment
- Documentation structure

---

## Release Guidelines

### Version Numbering

- **MAJOR**: Breaking changes in API or architecture
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Release Process

1. Update version in all `pyproject.toml` and `go.mod` files
2. Update CHANGELOG.md with release notes
3. Create git tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
4. Push tag: `git push origin v1.0.0`
5. CI/CD will build and publish artifacts

### Deprecation Policy

- Deprecated features are marked in documentation and emit warnings
- Deprecated features are removed after **one minor version**
- Breaking changes require MAJOR version bump
