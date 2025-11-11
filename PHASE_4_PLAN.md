# Phase 4: Production Hardening - Implementation Plan

**Start Date:** TBD (After Phase 3 staging validation)
**Duration:** 3-4 weeks
**Goal:** Production readiness, security hardening, and scale testing

## Executive Summary

Phase 4 focuses on hardening Sentinel for production deployment with enterprise-grade security, reliability testing, and comprehensive operational documentation. This phase ensures the platform can handle production workloads with confidence.

## Phase 4 Objectives

1. **Security Hardening** - Implement mTLS, RBAC, secrets management
2. **Reliability Testing** - Chaos engineering, load testing, failure scenarios
3. **Operational Readiness** - Monitoring, alerting, runbooks, troubleshooting
4. **Performance Optimization** - Profiling, bottleneck resolution, tuning
5. **Production Deployment** - Multi-environment setup, CI/CD for production

## Success Criteria

By the end of Phase 4:
- ✅ 99% of plans applied in <30s
- ✅ <1% rollback rate after canary
- ✅ Zero policy violations in production
- ✅ Pass all chaos and load tests
- ✅ Complete security audit
- ✅ Full operational documentation

## Implementation Roadmap

### Week 1: Security Hardening

#### 1.1 mTLS Between Services
**Priority:** Critical
**Effort:** 3-5 days

**Tasks:**
- [ ] Generate certificates with cert-manager or Vault PKI
- [ ] Configure mTLS for Control API ↔ InfraMind Adapter
- [ ] Configure mTLS for Pipeline Controller ↔ Control API
- [ ] Configure mTLS for Node Agents ↔ Control API
- [ ] Add certificate rotation automation
- [ ] Verify encrypted communication with Wireshark/tcpdump

**Files to Create:**
- `deploy/k8s/cert-manager.yaml` - Certificate manager setup
- `deploy/k8s/mtls-config.yaml` - mTLS configuration
- `services/*/app/core/mtls.py` - mTLS client/server helpers

**Testing:**
- Verify all inter-service communication uses TLS
- Test certificate rotation without downtime
- Validate certificate expiration alerts

#### 1.2 HashiCorp Vault Integration
**Priority:** High
**Effort:** 3-4 days

**Tasks:**
- [ ] Deploy Vault in dev/staging/prod
- [ ] Configure Vault authentication (Kubernetes auth)
- [ ] Migrate database credentials to Vault
- [ ] Migrate API keys to Vault (InfraMind, Kafka)
- [ ] Add dynamic secret rotation
- [ ] Implement Vault SDK in services

**Files to Create:**
- `deploy/k8s/vault.yaml` - Vault deployment
- `libs/sentinel-common/vault_client.py` - Vault SDK wrapper
- `services/*/app/core/secrets.py` - Secret loading from Vault

**Configuration:**
```python
# Example Vault integration
from sentinel_common import VaultClient

vault = VaultClient(
    url="https://vault.example.com",
    auth_method="kubernetes",
    role="sentinel-control-api"
)

db_password = vault.get_secret("database/sentinel/password")
```

#### 1.3 RBAC Enforcement
**Priority:** High
**Effort:** 2-3 days

**Tasks:**
- [ ] Define roles: viewer, operator, admin, system
- [ ] Implement RBAC middleware in Control API
- [ ] Add permission checks to all endpoints
- [ ] Integrate with external identity provider (OAuth2/OIDC)
- [ ] Add audit logging for all authenticated actions
- [ ] Create RBAC policy management API

**Roles:**
- **Viewer:** Read-only access to status and metrics
- **Operator:** Execute plans, trigger rollbacks (no policy changes)
- **Admin:** Full access including policy management
- **System:** Internal service-to-service communication

**Files to Create:**
- `services/control-api/app/core/rbac.py` - RBAC enforcement
- `services/control-api/app/models/rbac.py` - Role models
- `deploy/k8s/rbac-policies.yaml` - Kubernetes RBAC

### Week 2: Reliability & Chaos Testing

#### 2.1 Chaos Engineering Tests
**Priority:** High
**Effort:** 4-5 days

**Tasks:**
- [ ] Set up Chaos Mesh or Litmus Chaos
- [ ] Test pod failures (random pod kills)
- [ ] Test network partitions (split-brain scenarios)
- [ ] Test resource exhaustion (CPU, memory spikes)
- [ ] Test database failures (connection loss, recovery)
- [ ] Test Kafka failures (broker down, partition rebalancing)
- [ ] Verify system recovery and data consistency

**Chaos Scenarios:**
```yaml
# Example: Pod failure test
apiVersion: chaos-mesh.org/v1alpha1
kind: PodChaos
metadata:
  name: kill-control-api
spec:
  action: pod-kill
  mode: one
  selector:
    labelSelectors:
      app: control-api
  scheduler:
    cron: '@every 5m'
```

**Files to Create:**
- `tests/chaos/` - Chaos test scenarios
- `tests/chaos/pod_failures.yaml` - Pod kill tests
- `tests/chaos/network_partition.yaml` - Network chaos
- `tests/chaos/resource_stress.yaml` - Resource exhaustion
- `docs/chaos-testing.md` - Chaos testing guide

**Validation:**
- System continues operating during failures
- No data loss or corruption
- Graceful degradation of service
- Automatic recovery within SLA

#### 2.2 Load Testing
**Priority:** High
**Effort:** 3-4 days

**Tasks:**
- [ ] Set up load testing framework (Locust or k6)
- [ ] Test 100 concurrent plan submissions
- [ ] Test 1000+ managed workloads
- [ ] Test 50 canary deployments simultaneously
- [ ] Test 100 policy evaluations/second
- [ ] Test rate limiter under load
- [ ] Profile and optimize bottlenecks

**Load Test Scenarios:**
```python
# Example: Locust load test
from locust import HttpUser, task, between

class SentinelUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def submit_plan(self):
        self.client.post("/api/v1/action-plans", json={
            "decisions": [{"verb": "scale", "target": {...}, "params": {...}}],
            "source": "InfraMind"
        })

    @task
    def check_status(self):
        self.client.get("/api/v1/workloads")
```

**Files to Create:**
- `tests/load/locustfile.py` - Load test scenarios
- `tests/load/scenarios/` - Individual test scenarios
- `docs/performance-benchmarks.md` - Performance baselines

**Target Metrics:**
- 99% of plan submissions complete in <30s
- API p99 latency <500ms under load
- No memory leaks over 24h run
- Graceful degradation at 2x expected load

### Week 3: Operational Excellence

#### 3.1 Enhanced Monitoring & Alerting
**Priority:** High
**Effort:** 3-4 days

**Tasks:**
- [ ] Create Grafana dashboards for Phase 3 features
  - [ ] Canary deployment tracking
  - [ ] Rollback frequency and reasons
  - [ ] Rate limiting metrics
  - [ ] Change freeze enforcement
  - [ ] Health check scores over time
- [ ] Set up alerting rules (Alertmanager)
  - [ ] High rollback rate (>5% in 1 hour)
  - [ ] Policy violations detected
  - [ ] Failed canary deployments
  - [ ] Rate limiter saturation
  - [ ] Service health degradation
- [ ] Integrate with PagerDuty/Slack/Teams
- [ ] Create alert runbooks

**Dashboards:**
1. **SRE Overview** (existing - enhance)
   - Add Phase 3 panels
2. **Canary Deployments** (new)
   - Active canaries, traffic distribution, health scores
3. **Rollback Operations** (new)
   - Rollback frequency, reasons, success rate
4. **Policy Enforcement** (new)
   - Violations by type, freeze window hits, rate limits

**Files to Create:**
- `deploy/grafana/dashboards/canary.json`
- `deploy/grafana/dashboards/rollbacks.json`
- `deploy/grafana/dashboards/policies.json`
- `deploy/prometheus/alerts/phase3.rules.yml`

#### 3.2 Operator Runbooks
**Priority:** Medium
**Effort:** 2-3 days

**Tasks:**
- [ ] Write incident response procedures
- [ ] Document common failure scenarios
- [ ] Create troubleshooting guides
- [ ] Write operational procedures (backup, restore, upgrade)
- [ ] Document SLO definitions and error budgets

**Runbooks to Create:**
```
docs/runbooks/
├── incident-response.md          # On-call procedures
├── troubleshooting/
│   ├── high-rollback-rate.md    # Too many rollbacks
│   ├── canary-stuck.md          # Canary not progressing
│   ├── policy-violations.md     # Unexpected policy blocks
│   ├── rate-limit-saturation.md # Rate limits hit frequently
│   └── health-check-failures.md # False positive health checks
├── operations/
│   ├── backup-restore.md        # Data backup procedures
│   ├── upgrade-guide.md         # Zero-downtime upgrades
│   ├── scaling-guide.md         # Scale services for load
│   └── disaster-recovery.md     # DR procedures
└── slo-guide.md                 # SLO definitions
```

**Content Example:**
```markdown
# Runbook: High Rollback Rate

## Symptoms
- >5% of deployments rolled back in 1 hour
- Alertmanager firing: `HighRollbackRate`

## Investigation
1. Check Grafana: Rollback Operations dashboard
2. Identify common failure pattern (health checks, errors)
3. Review recent changes (deployments, policy updates)

## Resolution
1. If health checks too sensitive: Adjust min_health_score
2. If bad deployment: Manually rollback to known-good version
3. If policy issue: Review and adjust policies
4. If infrastructure: Check cluster health

## Prevention
- Review health check thresholds quarterly
- Implement staging environment for validation
- Use shadow mode before prod deployments
```

#### 3.3 Architecture Decision Records (ADRs)
**Priority:** Medium
**Effort:** 2 days

**Tasks:**
- [ ] Document key architectural decisions
- [ ] Explain trade-offs and alternatives considered
- [ ] Create ADR template

**ADRs to Create:**
```
docs/adr/
├── 001-microservices-architecture.md
├── 002-grpc-for-inframind.md
├── 003-policy-engine-design.md
├── 004-canary-vs-blue-green.md
├── 005-rate-limiter-implementation.md
├── 006-health-check-scoring.md
└── 007-shadow-mode-design.md
```

### Week 4: Performance & Production Deployment

#### 4.1 Performance Optimization
**Priority:** High
**Effort:** 3-4 days

**Tasks:**
- [ ] Profile services with py-spy or cProfile
- [ ] Identify and fix bottlenecks
- [ ] Optimize database queries (add indexes, caching)
- [ ] Implement connection pooling
- [ ] Add Redis for distributed rate limiting
- [ ] Tune Kubernetes resource requests/limits
- [ ] Optimize container images (multi-stage builds)

**Optimization Targets:**
- Control API: <200ms p99 latency
- Policy evaluation: <50ms per plan
- Database queries: <10ms p95
- Container startup: <30s
- Memory usage: <512MB per service at idle

#### 4.2 Blue/Green Deployment Support (Deferred from Phase 3)
**Priority:** Medium
**Effort:** 2-3 days

**Tasks:**
- [ ] Implement BlueGreenDeploymentController
- [ ] Add traffic switching logic
- [ ] Integrate with service mesh or Ingress
- [ ] Add instant rollback capability
- [ ] Write tests for blue/green strategy

**File to Create:**
- `libs/k8s-driver/sentinel_k8s/blue_green.py`

#### 4.3 Multi-Environment Deployment
**Priority:** High
**Effort:** 2-3 days

**Tasks:**
- [ ] Create environment-specific configs (dev, staging, prod)
- [ ] Set up GitOps workflow (ArgoCD or Flux)
- [ ] Configure production Kubernetes clusters
- [ ] Set up production databases with replication
- [ ] Configure production observability stack
- [ ] Implement automated deployment pipeline
- [ ] Create environment promotion process

**Environments:**
```
environments/
├── dev/                    # Local development
│   ├── config.yaml
│   └── kustomization.yaml
├── staging/                # Pre-production testing
│   ├── config.yaml
│   └── kustomization.yaml
└── production/             # Production
    ├── config.yaml
    ├── kustomization.yaml
    └── sealed-secrets.yaml
```

## Dependencies & Integration

### External Services Required

1. **HashiCorp Vault**
   - Deployment: Kubernetes or external
   - Purpose: Secrets management
   - Setup: ~1 day

2. **Chaos Mesh / Litmus Chaos**
   - Deployment: Kubernetes operator
   - Purpose: Chaos testing
   - Setup: ~0.5 days

3. **Load Testing Tool (Locust/k6)**
   - Deployment: Standalone or Kubernetes
   - Purpose: Performance testing
   - Setup: ~0.5 days

4. **Redis (Optional)**
   - Deployment: Kubernetes or managed service
   - Purpose: Distributed rate limiting
   - Setup: ~0.5 days

5. **Service Mesh (Optional)**
   - Options: Istio, Linkerd
   - Purpose: Advanced traffic control, mTLS
   - Setup: 2-3 days

## Migration & Upgrade Path

### From v0.3.0 to v0.4.0

**Breaking Changes:**
- mTLS required for inter-service communication
- Secrets must be migrated to Vault
- RBAC enforcement enabled (requires authentication)

**Migration Steps:**
1. Deploy Vault and migrate secrets
2. Enable mTLS with auto-rotation
3. Update service configurations for Vault
4. Enable RBAC and configure roles
5. Update client applications for authentication
6. Verify all services communicating securely

**Rollback Plan:**
- Keep v0.3.0 running in parallel during migration
- Test all workflows in staging first
- Have automated rollback scripts ready
- Monitor error rates closely during migration

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| mTLS misconfiguration breaks services | Medium | High | Extensive testing, gradual rollout |
| Vault downtime blocks operations | Low | High | High-availability Vault deployment, caching |
| Chaos tests cause production incidents | Low | Medium | Run in isolated test cluster first |
| Load tests overwhelm infrastructure | Medium | Medium | Start with low load, gradually increase |
| RBAC locks out legitimate users | Low | High | Admin override mechanism, comprehensive testing |
| Performance regressions | Medium | Medium | Baseline metrics before optimization |

## Testing Strategy

### Unit Tests
- [ ] RBAC middleware tests
- [ ] Vault client tests
- [ ] mTLS connection tests
- [ ] Blue/green controller tests

### Integration Tests
- [ ] End-to-end with mTLS enabled
- [ ] Vault integration tests
- [ ] RBAC policy enforcement tests
- [ ] Multi-service authentication tests

### Chaos Tests
- [ ] Pod failure recovery
- [ ] Network partition handling
- [ ] Database connection loss
- [ ] Kafka broker failures

### Load Tests
- [ ] 100 concurrent requests
- [ ] 1000 managed workloads
- [ ] 50 simultaneous canaries
- [ ] Rate limiter saturation

### Security Tests
- [ ] mTLS verification
- [ ] RBAC bypass attempts
- [ ] Secret exposure checks
- [ ] Vulnerability scanning (Trivy)

## Success Metrics

### Performance Targets
- API latency: p99 <500ms
- Plan execution: 99% complete in <30s
- Policy evaluation: <50ms per plan
- Canary rollout: 0% → 100% in <60 minutes

### Reliability Targets
- Service uptime: 99.9%
- Rollback rate: <1% of deployments
- Failed plan rate: <0.1%
- Recovery time: <5 minutes from failures

### Security Targets
- All traffic encrypted with mTLS
- Zero secrets in environment variables
- All API calls authenticated and authorized
- Zero critical/high vulnerabilities

## Deliverables Checklist

### Code
- [ ] mTLS implementation (all services)
- [ ] Vault integration (all services)
- [ ] RBAC middleware and models
- [ ] Blue/green deployment controller
- [ ] Redis-backed rate limiter (optional)

### Infrastructure
- [ ] Vault deployment manifests
- [ ] mTLS certificate management
- [ ] Chaos Mesh installation
- [ ] Multi-environment configs

### Documentation
- [ ] Operator runbooks (8+ runbooks)
- [ ] Architecture decision records (7+ ADRs)
- [ ] Security documentation
- [ ] Performance tuning guide
- [ ] Disaster recovery procedures

### Testing
- [ ] Chaos test scenarios (5+ scenarios)
- [ ] Load test suite (Locust/k6)
- [ ] Security test suite
- [ ] Upgrade/rollback procedures

### Monitoring
- [ ] 4 new Grafana dashboards
- [ ] Phase 4 alert rules
- [ ] PagerDuty/Slack integration
- [ ] SLO definitions and tracking

## Timeline Estimate

**Total Duration:** 3-4 weeks

```
Week 1: Security Hardening
├── Days 1-3: mTLS implementation
├── Days 4-5: Vault integration
└── Days 6-7: RBAC enforcement

Week 2: Reliability Testing
├── Days 8-11: Chaos engineering setup and tests
└── Days 12-14: Load testing and optimization

Week 3: Operational Readiness
├── Days 15-17: Monitoring, alerting, dashboards
├── Days 18-19: Runbooks and troubleshooting guides
└── Day 20-21: ADRs and documentation

Week 4: Production Deployment
├── Days 22-24: Performance optimization
├── Day 25: Blue/green deployment
└── Days 26-28: Multi-environment setup and deployment
```

## Phase 4 Completion Criteria

Phase 4 is complete when:
- ✅ All security features implemented and tested
- ✅ Chaos tests pass with graceful degradation
- ✅ Load tests meet performance targets
- ✅ Complete operational documentation
- ✅ Production environment deployed and validated
- ✅ Security audit passed
- ✅ 99.9% uptime demonstrated in staging for 1 week

## Next: Phase 5 Preview

After Phase 4, Sentinel will be production-ready. Phase 5 will focus on:
- **Agent Orchestration** - PatchBot integration for automated fixes
- **Intelligent Remediation** - AI-driven failure resolution
- **Advanced ML Integration** - Custom optimization models
- **Multi-Tenancy** - Tenant isolation and quotas

See **PHASE_5_PLAN.md** (to be created after Phase 4 completion).

---

**Last Updated:** November 11, 2025
**Status:** Planning - Awaiting Phase 3 validation
**Next Review:** After Phase 3 staging deployment
