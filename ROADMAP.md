# Sentinel Roadmap

This roadmap outlines the planned development phases for Sentinel.

## Phase 0: Scaffolding (Weeks 1-2) ✓ In Progress

**Goal:** Establish project foundation and development infrastructure

- [x] Repository structure and organization
- [x] Service skeletons (Control API, Pipeline Controller, InfraMind Adapter, Node Agent)
- [x] Shared library structure (policy-engine, k8s-driver, sentinel-common)
- [x] gRPC protobuf definitions
- [x] Development tooling (Makefile, linting, formatting)
- [ ] CI/CD pipeline (Jenkins/GitHub Actions)
- [ ] Local development environment (docker-compose)
- [ ] Basic Helm chart structure
- [ ] Container build pipeline with SBOM and signing

**Success Criteria:**
- All services can be built and started locally
- CI pipeline runs tests and builds containers
- Development environment is fully automated

---

## Phase 1: Orchestration + Observability (Weeks 3-5)

**Goal:** Implement core orchestration and telemetry capabilities

### Kubernetes Driver + Basic Deployments
- Multi-cluster kubeconfig loader
- Deployment/Job/StatefulSet creation with labels
- Scale operations and status watching
- Idempotent reconciliation loop

### Observability Stack
- Prometheus setup with scrape configs
- Grafana dashboards (SRE Overview, GPU Fleet, Workload Health)
- Kafka event bus for structured events
- OpenTelemetry tracing integration
- MLflow for experiment tracking

### Policy Engine v0
- Rule DSL definition and parser
- Policy evaluation engine
- SLA, rate limit, and cost ceiling enforcement
- Dry-run mode for policy testing

**Success Criteria:**
- Deploy workload to K8s cluster via API
- Scale workload up/down with policy enforcement
- Metrics visible in Prometheus and Grafana
- Events flowing through Kafka

**Deliverables:**
- Working K8s driver with basic CRUD operations
- Prometheus + Grafana + Kafka stack deployed
- Policy engine with basic rules
- Integration tests for deployment lifecycle

---

## Phase 2: InfraMind Integration (Weeks 6-7)

**Goal:** Close the feedback loop with InfraMind's predictive brain

### Telemetry Adapter
- Batch and filter telemetry from Prometheus/Kafka
- Stream telemetry to InfraMind via gRPC
- Handle backpressure and retry logic

### Decision API Client
- gRPC client for InfraMind Decision API
- Receive and validate ActionPlans
- Queue plans for execution
- Track plan acknowledgments and outcomes

### Plan Execution Pipeline
- Apply ActionPlans with guardrails
- Audit all plan executions
- Feedback loop to InfraMind

**Success Criteria:**
- Telemetry flowing from Sentinel to InfraMind
- InfraMind can submit ActionPlans
- Plans executed with audit trail
- Closed feedback loop operational

**Deliverables:**
- InfraMind Adapter service
- gRPC integration tested with mock InfraMind
- E2E test: metric → prediction → action → feedback

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
