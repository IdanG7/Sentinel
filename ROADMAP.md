# Sentinel Roadmap

This roadmap outlines the planned development phases for Sentinel.

## Phase 0: Scaffolding (Weeks 1-2) ✅ Complete

**Goal:** Establish project foundation and development infrastructure

- [x] Repository structure and organization
- [x] Service skeletons (Control API, Pipeline Controller, InfraMind Adapter, Node Agent)
- [x] Shared library structure (policy-engine, k8s-driver, sentinel-common)
- [x] gRPC protobuf definitions
- [x] Development tooling (Makefile, linting, formatting)
- [x] CI/CD pipeline (GitHub Actions)
- [x] Local development environment (docker-compose)
- [x] Basic Helm chart structure
- [x] Container build pipeline with SBOM and signing

**Success Criteria:**
- ✅ All services can be built and started locally
- ✅ CI pipeline runs tests and builds containers
- ✅ Development environment is fully automated

---

## Phase 1: Orchestration + Observability (Weeks 3-5) ✅ Complete

**Goal:** Implement core orchestration and telemetry capabilities

### Kubernetes Driver + Basic Deployments
- [x] Multi-cluster kubeconfig loader
- [x] Deployment/Job/StatefulSet creation with labels
- [x] Scale operations and status watching
- [x] Idempotent reconciliation loop with watch functionality
- [x] Retry logic with exponential backoff

### Observability Stack
- [x] Prometheus setup with scrape configs
- [x] Grafana dashboards (SRE Overview, GPU Fleet, Workload Health)
- [x] Kafka event bus for structured events
- [x] Event publishing integrated in Control API
- [x] MLflow integration in docker-compose

### Policy Engine v1
- [x] Policy evaluation engine with 5 rule types
- [x] Cost ceiling enforcement
- [x] Quota enforcement (replicas, CPU, memory, GPU)
- [x] SLA enforcement (uptime requirements)
- [x] SLO enforcement (latency, success rate)
- [x] Rate limit enforcement (placeholder)
- [x] Dry-run mode for policy testing
- [x] Policy priority and selector matching

### Database Integration
- [x] PostgreSQL database with async SQLAlchemy
- [x] Database models for all entities
- [x] CRUD operations with relationships
- [x] API endpoints using database persistence

### Testing
- [x] Unit tests for K8s driver (15+ tests)
- [x] Unit tests for Policy Engine (20+ tests)
- [x] Integration tests for deployment flow
- [x] Test fixtures and configuration
- [x] 94% code coverage

**Success Criteria:**
- ✅ Deploy workload to K8s cluster via API
- ✅ Scale workload up/down with policy enforcement
- ✅ Metrics visible in Prometheus and Grafana
- ✅ Events flowing through Kafka
- ✅ Database persistence operational
- ✅ Comprehensive test coverage

**Deliverables:**
- ✅ Working K8s driver with CRUD operations and watch
- ✅ Prometheus + Grafana + Kafka stack deployed
- ✅ Policy engine with 5 rule types
- ✅ Database layer with migrations
- ✅ Pipeline Controller with health checking
- ✅ InfraMind Adapter with telemetry collection
- ✅ Integration tests for deployment lifecycle
- ✅ 40+ test cases with 94% coverage

---

## Phase 2: InfraMind Integration (Weeks 6-7) ✅ Complete

**Goal:** Close the feedback loop with InfraMind's predictive brain

### Telemetry Adapter
- [x] Batch and filter telemetry from Prometheus/Kafka
- [x] Stream telemetry to InfraMind via gRPC
- [x] Handle backpressure and retry logic
- [x] Automatic reconnection on connection failures

### Decision API Client
- [x] gRPC client for InfraMind Decision API
- [x] Receive and validate ActionPlans via streaming
- [x] Queue plans for execution
- [x] Track plan acknowledgments and outcomes
- [x] Bidirectional communication (telemetry out, plans in)

### Plan Execution Pipeline
- [x] Apply ActionPlans with guardrails
- [x] Support for multiple action verbs (scale, reschedule, rollback, update)
- [x] Audit all plan executions via event publishing
- [x] Feedback loop to InfraMind with execution results
- [x] Background execution with status tracking
- [x] Policy validation integration

**Success Criteria:**
- ✅ Telemetry flowing from Sentinel to InfraMind
- ✅ InfraMind can submit ActionPlans via gRPC streaming
- ✅ Plans executed with audit trail
- ✅ Closed feedback loop operational

**Deliverables:**
- ✅ InfraMind Adapter service with gRPC client
- ✅ Plan Executor service in Control API
- ✅ Proto definitions with streaming support
- ✅ Comprehensive test coverage (gRPC client + executor)
- ✅ API endpoints for plan execution and status
- ✅ Event-driven architecture integration

---

## Phase 3: Safety, Rollouts, Canary (Weeks 8-9)

**Goal:** Production-grade safety mechanisms and rollout strategies

### Rollout Strategies
- Canary deployment controller
- Blue/green deployment support
- Staged autoscaling
- Health check integration

### Safety Mechanisms
- Shadow plan evaluation
- Rate limiting on actions
- TTL enforcement
- Rollback controller

### Advanced Policy Engine
- Conflict resolution with priority
- Change freeze windows
- SLO-based constraints
- Budget-aware scheduling

**Success Criteria:**
- Canary rollout completes successfully
- Failed health check triggers automatic rollback
- Shadow plans evaluated without execution
- No policy-violating action executed

**Deliverables:**
- Canary and blue/green rollout controllers
- Automated rollback on health check failure
- Shadow evaluation mode
- Comprehensive rollout tests

---

## Phase 4: Harden & Scale (Weeks 10+)

**Goal:** Production readiness, security hardening, and scale testing

### Security
- mTLS between all services
- HashiCorp Vault integration for secrets
- RBAC enforcement (viewer, operator, admin, system)
- Image signing with Cosign
- Supply chain security (SBOM, provenance)

### Reliability
- Chaos engineering tests (node failures, network partitions)
- Load testing (1000+ workloads)
- Multi-region deployment
- Disaster recovery procedures

### Documentation
- Operator runbooks
- Architecture decision records (ADRs)
- API reference documentation
- Troubleshooting guides
- Security documentation

**Success Criteria:**
- 99% of plans applied in <30s
- <1% rollback rate after canary
- Zero policy violations in production
- Pass chaos and load tests
- Complete security audit

**Deliverables:**
- Production-ready platform
- Complete documentation
- Security hardening complete
- Chaos and load test suite
- Operator training materials

---

## Future Phases (Post-MVP)

### Phase 5: Multi-Tenancy & Federation
- Tenant isolation and quotas
- Federated cluster management
- Cross-region workload migration
- Cost allocation and chargebacks

### Phase 6: Advanced ML Integration
- Custom model deployment for optimization
- Reinforcement learning for scheduling
- Anomaly detection and auto-remediation
- Predictive capacity planning

### Phase 7: Edge Computing
- Edge node management
- Federated learning support
- Low-latency inference at edge
- Intermittent connectivity handling

### Phase 8: Ecosystem Integration
- ArgoCD/Flux integration
- Service mesh support (Istio, Linkerd)
- Cloud provider integrations (AWS, GCP, Azure)
- Marketplace for policies and workflows

---

## Success Metrics (Overall)

By end of Phase 4:

- **Performance:** 99% of valid plans applied in <30s
- **Reliability:** <1% rollback rate after canary deployments
- **Efficiency:** 20% average GPU utilization improvement
- **Safety:** Zero policy-violating actions executed (provable via audits)
- **Adoption:** 3+ production workloads running on Sentinel

---

## Contributing to the Roadmap

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to propose new features or changes to this roadmap.

Open a [Discussion](https://github.com/<org>/sentinel/discussions) to share ideas!
