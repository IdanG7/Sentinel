# Incident Response Runbook

## Overview

This runbook covers immediate response procedures for Sentinel incidents.

## On-Call Setup

**Prerequisites:**
- Access to Kubernetes clusters (kubeconfig)
- Access to Grafana/Prometheus
- Access to Vault (for secrets)
- Kubectl, helm, curl installed
- PagerDuty/Slack notifications configured

## Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P0 | System down | <15 min | Control API completely unavailable |
| P1 | Critical degradation | <30 min | 50%+ error rate, data loss |
| P2 | Significant impact | <2 hours | High latency, partial outage |
| P3 | Minor impact | <1 day | Single feature broken |

## Immediate Response (First 5 Minutes)

### 1. Acknowledge Alert
```bash
# Acknowledge in PagerDuty/Slack
# Note time of acknowledgment
```

### 2. Assess Severity
Check Grafana SRE Overview dashboard: http://grafana:3000

**Key indicators:**
- API error rate >5% → P1
- API latency p99 >2s → P1
- All pods down → P0
- InfraMind disconnect → P2

### 3. Check System Health

```bash
# Check pod status
kubectl get pods -n sentinel-system

# Check recent events
kubectl get events -n sentinel-system --sort-by='.lastTimestamp' | tail -20

# Check Control API logs
kubectl logs -n sentinel-system -l app=control-api --tail=100

# Check resource usage
kubectl top pods -n sentinel-system
```

### 4. Quick Diagnostics

```bash
# Test API health
curl -f http://control-api:8000/health

# Check database connectivity
kubectl exec -it postgresql-0 -n sentinel-system -- psql -U sentinel -c 'SELECT 1'

# Check Prometheus
curl -f http://prometheus:9090/-/healthy

# Check Kafka
kubectl exec -it kafka-0 -n sentinel-system -- kafka-broker-api-versions.sh --bootstrap-server localhost:9092
```

## Common Incidents

### Control API Down (P0)

**Symptoms:**
- All API requests return 503 or timeout
- Pods in CrashLoopBackOff

**Investigation:**
```bash
# Check pod status
kubectl get pods -n sentinel-system -l app=control-api

# Check logs for errors
kubectl logs -n sentinel-system -l app=control-api --tail=100

# Check recent changes
kubectl rollout history deployment/control-api -n sentinel-system

# Check resource constraints
kubectl describe pod -n sentinel-system -l app=control-api
```

**Common Causes:**
1. Database connection failure
2. OOM kill
3. Bad deployment
4. Certificate expiration

**Resolution:**
```bash
# If OOM: Increase memory limits
kubectl set resources deployment/control-api -n sentinel-system \
  --limits=memory=2Gi --requests=memory=1Gi

# If bad deployment: Rollback
kubectl rollout undo deployment/control-api -n sentinel-system

# If DB connection: Check PostgreSQL
kubectl get pods -n sentinel-system -l app=postgresql

# If cert expired: Renew certificates
kubectl get certificates -n sentinel-system
kubectl delete certificate control-api-mtls -n sentinel-system  # Cert-manager will recreate
```

### High Error Rate (P1)

**Symptoms:**
- API error rate >5%
- Many 500 errors in logs

**Investigation:**
```bash
# Check error types
kubectl logs -n sentinel-system -l app=control-api --tail=1000 | grep ERROR

# Check Prometheus for error patterns
# Query: rate(http_requests_total{status=~"5.."}[5m])

# Check database slow queries
kubectl exec -it postgresql-0 -n sentinel-system -- \
  psql -U sentinel -c "SELECT query, calls, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"
```

**Common Causes:**
1. Database connection pool exhausted
2. Slow queries causing timeouts
3. Downstream service (InfraMind) unavailable
4. Memory leak

**Resolution:**
```bash
# Increase DB connection pool
kubectl set env deployment/control-api -n sentinel-system \
  DATABASE_POOL_SIZE=50

# Restart to clear memory leak
kubectl rollout restart deployment/control-api -n sentinel-system

# Check InfraMind connectivity
curl -f http://inframind:8081/health
```

### InfraMind Disconnected (P2)

**Symptoms:**
- No action plans being generated
- InfraMind health check failing

**Investigation:**
```bash
# Check InfraMind adapter logs
kubectl logs -n sentinel-system -l app=infra-adapter --tail=100

# Check InfraMind service
kubectl get pods -n sentinel-system -l app=inframind

# Test connectivity
kubectl exec -it -n sentinel-system deploy/infra-adapter -- \
  curl -f http://inframind:8081/health
```

**Resolution:**
```bash
# Restart InfraMind
kubectl rollout restart deployment/inframind -n sentinel-system

# Restart adapter
kubectl rollout restart deployment/infra-adapter -n sentinel-system

# Check network policies
kubectl get networkpolicies -n sentinel-system

# Verify mTLS certificates
kubectl get certificates -n sentinel-system
```

### Database Full (P1)

**Symptoms:**
- Write operations failing
- Disk usage at 95%+

**Investigation:**
```bash
# Check disk usage
kubectl exec -it postgresql-0 -n sentinel-system -- df -h

# Check database size
kubectl exec -it postgresql-0 -n sentinel-system -- \
  psql -U sentinel -c "SELECT pg_size_pretty(pg_database_size('sentinel'))"

# Check largest tables
kubectl exec -it postgresql-0 -n sentinel-system -- \
  psql -U sentinel -c "SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables ORDER BY pg_total_relation_size(relid) DESC"
```

**Resolution:**
```bash
# Emergency: Delete old audit logs
kubectl exec -it postgresql-0 -n sentinel-system -- \
  psql -U sentinel -c "DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '30 days'"

# Vacuum database
kubectl exec -it postgresql-0 -n sentinel-system -- \
  psql -U sentinel -c "VACUUM FULL"

# Long-term: Increase PVC size
kubectl patch pvc postgresql-data -n sentinel-system \
  -p '{"spec":{"resources":{"requests":{"storage":"100Gi"}}}}'

# Configure log retention policy
kubectl set env deployment/control-api -n sentinel-system \
  AUDIT_LOG_RETENTION_DAYS=30
```

## Escalation Path

1. **L1 (On-call SRE)**: Initial response, common issues
2. **L2 (Senior SRE)**: Complex issues, architecture decisions
3. **L3 (Engineering)**: Code bugs, design flaws
4. **L4 (Architecture/CTO)**: System redesign, vendor engagement

**Escalation triggers:**
- Incident >1 hour unresolved
- Uncertain root cause
- Requires code changes
- Multiple services affected

## Post-Incident

### 1. Incident Report (within 24h)

**Required fields:**
- Start time and detection time
- Impact (users affected, revenue lost)
- Root cause
- Timeline of actions
- Resolution
- Follow-up items

### 2. Post-Mortem (within 1 week)

**Blameless review covering:**
- What happened
- Why it happened
- What went well
- What could be improved
- Action items with owners

**Template:** `docs/templates/post-mortem.md`

### 3. Follow-Up Actions

Create tickets for:
- Monitoring improvements
- Runbook updates
- Code fixes
- Architecture changes

## Communication Templates

### Initial Update (within 15 min)
```
🚨 Incident: Sentinel Control API Degraded (P1)
Status: Investigating
Impact: High API latency affecting 50% of requests
ETA: Under investigation
Next update: In 30 minutes
```

### Resolution Update
```
✅ Resolved: Sentinel Control API Degraded
Duration: 45 minutes
Cause: Database connection pool exhausted
Fix: Increased pool size and restarted API
Next steps: Post-mortem scheduled for Thursday
```

## Useful Commands Cheat Sheet

```bash
# Quick status check
kubectl get pods -n sentinel-system

# Recent errors
kubectl logs -n sentinel-system -l app=control-api --tail=100 | grep ERROR

# Resource usage
kubectl top pods -n sentinel-system

# Recent events
kubectl get events -n sentinel-system --sort-by='.lastTimestamp' | tail -20

# Restart service
kubectl rollout restart deployment/control-api -n sentinel-system

# Rollback deployment
kubectl rollout undo deployment/control-api -n sentinel-system

# Scale up
kubectl scale deployment/control-api -n sentinel-system --replicas=5

# Check health endpoints
for svc in control-api pipeline-controller infra-adapter; do
  echo "=== $svc ==="
  kubectl exec -n sentinel-system deploy/$svc -- curl -s http://localhost:8000/health | jq
done
```

## Emergency Contacts

| Role | Name | Slack | Phone | Escalation |
|------|------|-------|-------|------------|
| On-Call SRE | Rotation | @oncall-sre | PagerDuty | Primary |
| SRE Lead | Alice | @alice | +1-555-0001 | L2 |
| Platform Eng | Bob | @bob | +1-555-0002 | L3 |
| CTO | Charlie | @charlie | +1-555-0003 | L4 |

## Additional Resources

- [High Rollback Rate Runbook](./high-rollback-rate.md)
- [Database Troubleshooting](./database-issues.md)
- [InfraMind Connectivity](./inframind-connectivity.md)
- [Grafana Dashboards](http://grafana:3000/dashboards)
- [Prometheus Alerts](http://prometheus:9090/alerts)
