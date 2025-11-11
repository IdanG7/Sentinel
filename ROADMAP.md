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

## Phase 3: Safety, Rollouts, Canary (Weeks 8-9) ✅ Complete

**Goal:** Production-grade safety mechanisms and rollout strategies

### Rollout Strategies
- [x] Canary deployment controller
- [ ] Blue/green deployment support (deferred to Phase 4)
- [ ] Staged autoscaling (deferred to Phase 4)
- [x] Health check integration

### Safety Mechanisms
- [x] Shadow plan evaluation
- [x] Rate limiting on actions
- [x] TTL enforcement (existing)
- [x] Rollback controller

### Advanced Policy Engine
- [ ] Conflict resolution with priority (deferred - current priority system works)
- [x] Change freeze windows
- [x] SLO-based constraints (existing)
- [ ] Budget-aware scheduling (deferred to Phase 4)

**Success Criteria:**
- ✅ Canary rollout completes successfully
- ✅ Failed health check triggers automatic rollback
- ✅ Shadow plans evaluated without execution
- ✅ No policy-violating action executed
- ✅ Rate limiting enforced with state tracking
- ✅ Change freeze windows block deployments

**Deliverables:**
- ✅ Canary deployment controller with progressive traffic shifting
- ✅ Automated rollback on health check failure
- ✅ Shadow evaluation mode (policy + executor)
- ✅ Health check framework with scoring
- ✅ Rate limiter with sliding window algorithm
- ✅ Change freeze with timezone support
- ⏳ Comprehensive rollout tests (pending)
- ⏳ Blue/green rollout controller (moved to Phase 4)

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

## Phase 5: Intelligent Agent Orchestration (PatchBot Integration) (Weeks 11-13)

**Goal:** Transform Sentinel from an orchestration platform into an AI-driven agent controller that manages autonomous remediation modules, starting with PatchBot for automatic failure resolution.

**Objective:** Enable Sentinel to detect recurring CI/CD or system failures and invoke specialized AI agents (starting with PatchBot) to fix or suggest resolutions automatically, creating a self-healing development and operations pipeline.

### Agent Controller Service
- **Agent Registry:** Catalog of available autonomous agents with capabilities, versions, and health status
- **Agent Lifecycle Management:** Start, stop, pause, resume, upgrade agents
- **Sandboxing & Isolation:** Secure execution environments with resource limits (CPU, memory, network)
- **Agent Scheduling:** Queue-based task distribution with priority and rate limiting
- **Agent Monitoring:** Real-time metrics, logs aggregation, and failure detection
- **Agent API Gateway:** Unified interface for agent invocation and result retrieval

### PatchBot Integration Pipeline
- **Logs Ingestion Layer:**
  - Consume CI/CD failure logs from GitHub Actions, GitLab CI, Jenkins
  - Parse and normalize log formats into structured failure events
  - Extract key signals: error messages, stack traces, failed commands, environment context

- **Failure Classification Engine:**
  - ML-based categorization of failure types (linting, test failures, build errors, deployment issues)
  - Pattern matching for known issue signatures
  - Severity assessment and urgency scoring
  - Deduplication of similar failures across time and repositories

- **Fix Generation Workflow:**
  - Invoke PatchBot agent with failure context and repository access
  - PatchBot analyzes codebase, dependencies, and historical fixes
  - Generate fix candidates with confidence scores
  - Validate fixes in isolated sandbox environment

- **Pull Request Creation:**
  - Automated PR generation with fix, tests, and explanation
  - Link to original failure logs and InfraMind analysis
  - Flag for human review with confidence threshold
  - Track PR lifecycle and merge outcomes

### Telemetry Correlation Layer
- **Bidirectional Data Flow:**
  - **InfraMind → Agent Controller:** Failure predictions, anomaly alerts, optimization opportunities
  - **Agent Outcomes → InfraMind:** Fix success rates, execution metrics, learning signals

- **Correlation Engine:**
  - Link InfraMind predictions to agent invocations
  - Track prediction accuracy vs. actual agent outcomes
  - Measure time-to-fix and success rates per failure type
  - Feed agent performance back to InfraMind for model improvement

- **Knowledge Graph:**
  - Build graph of failures → fixes → outcomes
  - Identify patterns and recurring issues
  - Suggest proactive fixes before failures occur

### Policy Extensions for Safe Auto-Remediation
- **Auto-Remediation Policies:**
  - **Rate Limits:** Max fixes per hour/day/week per repository
  - **Confidence Thresholds:** Only auto-merge fixes above X% confidence
  - **Blast Radius Control:** Limit simultaneous fixes across repositories
  - **Change Freeze Windows:** No auto-fixes during critical periods

- **Human-Review Gates:**
  - Mandatory review for high-risk changes (security, production configs)
  - Escalation paths for low-confidence fixes
  - Approval workflows with timeout policies

- **Rollback Plans:**
  - Automatic PR revert if CI fails after merge
  - Metrics-based rollback triggers (error rate spikes, performance degradation)
  - Cooldown periods after rollback before retry

- **Audit & Compliance:**
  - Immutable audit trail of all agent actions
  - Compliance checks for regulatory requirements
  - Monthly reports on agent activity and outcomes

### New Architecture Components

```
┌──────────────────────────────────────────────────────────────┐
│                     InfraMind (Brain)                         │
│  Failure Prediction ←→ Outcome Learning ←→ Optimization      │
└────────────────┬──────────────────────────┬──────────────────┘
                 │                          │
        ┌────────▼──────────┐      ┌────────▼─────────┐
        │  Action Plans     │      │ Failure Alerts   │
        └────────┬──────────┘      └────────┬─────────┘
                 │                          │
┌────────────────▼──────────────────────────▼─────────────────┐
│                   Sentinel (Executor)                         │
│                                                               │
│  Control API ──→ Policy Engine ──→ Pipeline Controller       │
│       │                                    │                  │
│       └──────┐                    ┌────────┴────────┐        │
│              │                    │                 │        │
│         K8s Driver          Node Agents      Agent Controller│
│                                              │                │
│                                   ┌──────────▼──────────┐    │
│                                   │   Agent Registry    │    │
│                                   │   - PatchBot        │    │
│                                   │   - LogAnalyzer     │    │
│                                   │   - ConfigOptimizer │    │
│                                   └──────────┬──────────┘    │
│                                              │                │
│                                   ┌──────────▼──────────┐    │
│                                   │  Execution Sandbox  │    │
│                                   │  (Isolated, Limited)│    │
│                                   └─────────────────────┘    │
└───────────────────────────────────────────────────────────────┘
         │                              │
         │                              │
┌────────▼────────┐          ┌──────────▼──────────┐
│  GitHub/GitLab  │          │   PatchBot Agent    │
│   CI/CD Logs    │◄─────────┤  - Fix Generation   │
│   PR Creation   │          │  - Test Validation  │
└─────────────────┘          │  - PR Submission    │
                             └─────────────────────┘
```

### Implementation Details

**Agent Controller Components:**
1. **Agent Executor Service** (`services/agent-controller/`)
   - Agent task queue (Redis/RabbitMQ)
   - Sandboxed execution runtime (Docker/gVisor)
   - Result aggregation and storage

2. **Agent SDK** (`libs/agent-sdk/`)
   - Python/Go SDK for agent development
   - Standard interfaces: `initialize()`, `execute(task)`, `cleanup()`
   - Built-in telemetry and logging

3. **PatchBot Agent** (`agents/patchbot/`)
   - LLM-powered code fix generation
   - Integration with git repositories
   - Test execution and validation
   - PR creation and management

**gRPC Protocol Extensions:**
```protobuf
service AgentController {
  rpc RegisterAgent(AgentInfo) returns (AgentId);
  rpc InvokeAgent(AgentTask) returns (stream AgentResult);
  rpc GetAgentStatus(AgentId) returns (AgentStatus);
  rpc CancelTask(TaskId) returns (Ack);
}

message AgentTask {
  string agent_id = 1;
  string task_type = 2;  // fix_ci_failure, optimize_config, etc.
  map<string, string> context = 3;
  bytes payload = 4;
  int32 timeout_seconds = 5;
  map<string, string> policy_overrides = 6;
}

message AgentResult {
  string task_id = 1;
  string status = 2;  // running, completed, failed
  float progress = 3;
  repeated Artifact artifacts = 4;  // generated files, PRs, logs
  map<string, float> metrics = 5;
  string error_message = 6;
}
```

**Database Schema Extensions:**
```sql
-- Agent registry
CREATE TABLE agents (
  id UUID PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  version VARCHAR(20) NOT NULL,
  capabilities JSONB NOT NULL,
  status VARCHAR(20) NOT NULL,
  health_score FLOAT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

-- Agent tasks and outcomes
CREATE TABLE agent_tasks (
  id UUID PRIMARY KEY,
  agent_id UUID REFERENCES agents(id),
  task_type VARCHAR(50) NOT NULL,
  context JSONB NOT NULL,
  status VARCHAR(20) NOT NULL,
  result JSONB,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_ms INTEGER,
  correlation_id UUID  -- Link to InfraMind prediction
);

-- Failure → Fix correlation
CREATE TABLE failure_fixes (
  id UUID PRIMARY KEY,
  failure_signature VARCHAR(255) NOT NULL,
  repository VARCHAR(255) NOT NULL,
  failure_type VARCHAR(50) NOT NULL,
  agent_task_id UUID REFERENCES agent_tasks(id),
  fix_pr_url VARCHAR(500),
  fix_confidence FLOAT,
  fix_success BOOLEAN,
  time_to_fix_seconds INTEGER,
  created_at TIMESTAMP
);
```

### Success Criteria
- ✅ Agent Controller operational with PatchBot registered
- ✅ PatchBot successfully fixes 3+ types of CI failures
- ✅ 70%+ fix success rate on linting and test failures
- ✅ Average time-to-PR under 5 minutes
- ✅ Zero unauthorized actions (all policy-compliant)
- ✅ Telemetry correlation shows InfraMind prediction → PatchBot fix link
- ✅ Human review workflow functional with approval gates

### Deliverables
- **Agent Controller Service:** Complete with registry, scheduling, sandboxing
- **PatchBot Agent:** Working implementation with GitHub integration
- **Failure Ingestion Pipeline:** CI/CD log parsing and classification
- **Policy Engine Extensions:** Auto-remediation policies and gates
- **Telemetry Correlation:** Bidirectional flow between InfraMind and agents
- **Documentation:** Agent development guide, PatchBot user manual, policy configuration guide
- **Tests:** Agent lifecycle tests, PatchBot integration tests, policy enforcement tests
- **Dashboards:** Agent performance metrics, fix success rates, time-to-resolution

### Risks & Mitigations
- **Risk:** Agent generates breaking changes
  - **Mitigation:** Sandbox validation, confidence thresholds, mandatory review for high-risk changes

- **Risk:** Agent overwhelms repositories with PRs
  - **Mitigation:** Rate limiting policies, cooldown periods, blast radius controls

- **Risk:** Security vulnerabilities in agent code
  - **Mitigation:** Isolated execution, restricted permissions, regular security audits

- **Risk:** InfraMind predictions are inaccurate
  - **Mitigation:** Feedback loop to improve models, human review gates, rollback mechanisms

---

## Future Phases (Post-Phase 5)

### Phase 6: Multi-Tenancy & Federation
- Tenant isolation and quotas
- Federated cluster management
- Cross-region workload migration
- Cost allocation and chargebacks

### Phase 7: Advanced ML Integration
- Custom model deployment for optimization
- Reinforcement learning for scheduling
- Anomaly detection and auto-remediation
- Predictive capacity planning

### Phase 8: Edge Computing
- Edge node management
- Federated learning support
- Low-latency inference at edge
- Intermittent connectivity handling

### Phase 9: Ecosystem Integration
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
