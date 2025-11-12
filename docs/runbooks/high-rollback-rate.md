# Runbook: High Rollback Rate

## Symptoms

- **Alert:** `HighRollbackRate` firing in Alertmanager
- **Condition:** >5% of deployments rolled back in 1 hour
- **Impact:** Failed changes, service instability, lost confidence in automation

## Severity

**P2** - Significant impact on deployment reliability

## Investigation Steps

### 1. Check Rollback Dashboard

Open Grafana → "Rollback Operations" dashboard

**Key metrics to check:**
- Rollback rate (last 1h, 24h, 7d)
- Most common rollback reasons
- Affected services/namespaces
- Correlation with deployment frequency

### 2. Query Recent Rollbacks

```bash
# Get recent rollback events
kubectl get events -n sentinel-system \
  --field-selector reason=RollbackTriggered \
  --sort-by='.lastTimestamp' | tail -20

# Check audit logs
curl -s "http://control-api:8000/api/v1/audits?action=rollback&limit=50" | jq '.[] | {timestamp, deployment, reason}'

# Query Prometheus
# rate(sentinel_deployments_rollback_total[1h])
```

### 3. Analyze Rollback Reasons

```bash
# Group rollbacks by reason
curl -s "http://control-api:8000/api/v1/audits?action=rollback" | \
  jq -r '.[].reason' | sort | uniq -c | sort -rn

# Common reasons:
# - health_check_failed
# - error_rate_exceeded
# - latency_threshold_exceeded
# - manual_rollback
```

### 4. Check Common Failure Patterns

```bash
# Check if rollbacks clustered around specific time
curl -s "http://control-api:8000/api/v1/audits?action=rollback" | \
  jq -r '.[].timestamp' | cut -d'T' -f1 | sort | uniq -c

# Check if specific services are affected
curl -s "http://control-api:8000/api/v1/audits?action=rollback" | \
  jq -r '.[].target.deployment' | sort | uniq -c | sort -rn
```

## Common Root Causes

### 1. Health Checks Too Sensitive

**Symptoms:**
- Rollbacks due to `health_check_failed`
- Services are actually healthy
- False positives in health endpoint

**Investigation:**
```bash
# Check health check configuration
kubectl get deployment <deployment-name> -n <namespace> -o yaml | grep -A 10 readinessProbe

# Check actual service health
kubectl exec -it <pod-name> -n <namespace> -- curl -v http://localhost:8000/health

# Review health check logs
kubectl logs -n <namespace> <pod-name> | grep health
```

**Resolution:**
```yaml
# Adjust health check thresholds
# In deployment YAML or via kubectl patch

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30  # Increase from 10
  periodSeconds: 10
  timeoutSeconds: 5
  successThreshold: 1
  failureThreshold: 5       # Increase from 3
```

**Sentinel-specific:**
```bash
# Update canary health threshold
curl -X PATCH http://control-api:8000/api/v1/deployments/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "canary": {
      "healthThreshold": 0.7,  # Lower from 0.9
      "healthCheckInterval": "30s"
    }
  }'
```

### 2. Bad Deployment Image

**Symptoms:**
- Multiple services rolling back
- Rollbacks started after recent release
- Errors in application logs

**Investigation:**
```bash
# Check recent image changes
kubectl rollout history deployment/<deployment-name> -n <namespace>

# Compare working vs failing image
kubectl describe deployment/<deployment-name> -n <namespace> | grep Image

# Check image scan results
trivy image ghcr.io/sentinel/control-api:v1.2.3
```

**Resolution:**
```bash
# Rollback to known-good image
kubectl set image deployment/<deployment-name> \
  <container-name>=ghcr.io/sentinel/control-api:v1.2.2 \
  -n <namespace>

# Or use Sentinel API
curl -X POST http://control-api:8000/api/v1/deployments/<id>/rollback \
  -H "Content-Type: application/json" \
  -d '{"targetVersion": "v1.2.2", "reason": "bad image"}'

# Block bad image in CI/CD
git revert <commit-hash>
```

### 3. Infrastructure Issues

**Symptoms:**
- Rollbacks across multiple unrelated services
- Started after infrastructure change
- Resource constraints in logs

**Investigation:**
```bash
# Check node health
kubectl get nodes
kubectl describe nodes | grep -A 5 "Conditions:"

# Check cluster events
kubectl get events --all-namespaces --sort-by='.lastTimestamp' | grep -i error

# Check resource pressure
kubectl top nodes
kubectl describe nodes | grep -A 5 "Allocated resources:"
```

**Resolution:**
```bash
# If node pressure: Cordon and drain
kubectl cordon <node-name>
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# If cluster overloaded: Scale down low-priority workloads
kubectl scale deployment/<deployment-name> --replicas=1 -n <namespace>

# If disk pressure: Clean up old images
kubectl exec -it <node> -- crictl rmi --prune
```

### 4. Policy Changes

**Symptoms:**
- Rollbacks due to policy violations
- Started after policy update
- Policy violation in audit logs

**Investigation:**
```bash
# Check recent policy changes
curl -s http://control-api:8000/api/v1/policies | jq '.[] | {name, updated_at}'

# Check policy violations
curl -s "http://control-api:8000/api/v1/audits?type=policy_violation" | \
  jq '.[] | {timestamp, policy, violation}'

# Check which policies are blocking deployments
curl -s http://control-api:8000/api/v1/policy-violations | \
  jq '.[] | {policy, deployment, reason}'
```

**Resolution:**
```bash
# Temporarily disable problematic policy
curl -X PATCH http://control-api:8000/api/v1/policies/<policy-id> \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Or adjust policy constraints
curl -X PATCH http://control-api:8000/api/v1/policies/<policy-id> \
  -H "Content-Type: application/json" \
  -d '{
    "rules": [{
      "type": "cost_ceiling",
      "constraint": {"max_cost_per_hour": 200}
    }]
  }'

# Review policy in staging first
curl -X POST http://control-api:8000/api/v1/policies/validate \
  -H "Content-Type: application/json" \
  -d @new-policy.json
```

### 5. Rate Limiter Issues

**Symptoms:**
- Many rollbacks in short time
- InfraMind generating too many plans
- Rate limiter saturation

**Investigation:**
```bash
# Check rate limiter stats
curl -s http://control-api:8000/api/v1/metrics | grep rate_limit

# Check InfraMind decision frequency
curl -s "http://control-api:8000/api/v1/audits?source=inframind" | \
  jq -r '.[].timestamp' | cut -d'T' -f2 | cut -d':' -f1 | sort | uniq -c

# Check for rate limit errors
kubectl logs -n sentinel-system -l app=control-api | grep "rate limit exceeded"
```

**Resolution:**
```bash
# Increase rate limits
curl -X PATCH http://control-api:8000/api/v1/policies/rate-limit \
  -H "Content-Type: application/json" \
  -d '{
    "max_changes_per_hour": 100,
    "max_changes_per_service": 10
  }'

# Reduce InfraMind decision frequency
kubectl set env deployment/infra-adapter -n sentinel-system \
  DECISION_INTERVAL_SECONDS=600  # 10 minutes instead of 5

# Review InfraMind confidence threshold
# Only apply high-confidence decisions
```

## Prevention Strategies

### 1. Improve Health Checks
- Review health check logic quarterly
- Add timeout and resource checks
- Use composite health scores
- Distinguish startup vs liveness

### 2. Enhanced Testing
- Staging environment for all changes
- Integration tests before production
- Canary by default
- Automated rollback testing

### 3. Shadow Mode
- Test InfraMind plans in shadow mode first
- Collect 48h of shadow data
- Review confidence scores
- Gradual rollout of new decision types

### 4. Better Monitoring
- Alert on health check failure rate
- Dashboard for canary success rate
- Track rollback reasons over time
- Correlation analysis with changes

### 5. Change Management
- Freeze windows for critical periods
- Gradual rollout across clusters
- Peer review for policy changes
- Automated policy testing

## Dashboards & Alerts

### Grafana Queries

```promql
# Rollback rate (1h)
rate(sentinel_deployments_rollback_total[1h])

# Rollback reasons
topk(5, sum by (reason) (sentinel_deployments_rollback_total))

# Services with most rollbacks
topk(10, sum by (service) (sentinel_deployments_rollback_total))

# Correlation with deployment frequency
rate(sentinel_deployments_total[1h]) / rate(sentinel_deployments_rollback_total[1h])
```

### Alert Configuration

```yaml
# Alert when rollback rate exceeds threshold
- alert: HighRollbackRate
  expr: rate(sentinel_deployments_rollback_total[1h]) > 0.05
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "High rollback rate detected"
    description: "{{ $value | humanizePercentage }} of deployments rolled back in last hour"
```

## Escalation

- **<15 min resolution:** Continue investigation
- **15-30 min:** Engage senior SRE
- **>30 min:** Incident call with engineering
- **Blocking deployments:** Page on-call engineering lead

## Follow-Up Actions

After resolution:
1. Document root cause
2. Update runbook with learnings
3. Create tickets for prevention
4. Review with team in post-mortem
5. Update monitoring/alerting
6. Test fixes in staging

## Related Runbooks

- [Canary Stuck](./canary-stuck.md)
- [Policy Violations](./policy-violations.md)
- [Health Check Failures](./health-check-failures.md)
- [Incident Response](./incident-response.md)
