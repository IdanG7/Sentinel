# Load Testing for Sentinel

## Overview

Load tests using Locust to validate Sentinel Control API performance and scalability.

## Installation

```bash
pip install locust
```

## Running Tests

### Interactive Mode (with Web UI)

```bash
cd /Users/idang/Projects/Sentinel
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

Then open http://localhost:8089 in your browser and configure:
- Number of users
- Spawn rate
- Host

### Headless Mode (CI/CD)

```bash
# Quick test: 50 users for 5 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=5m \
  --headless \
  --html=reports/load-test-report.html

# Stress test: 200 users for 30 minutes
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users=200 \
  --spawn-rate=10 \
  --run-time=30m \
  --headless \
  --html=reports/stress-test-report.html

# Specific user class only
locust -f tests/load/locustfile.py \
  --host=http://localhost:8000 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=10m \
  --headless \
  --user-classes InfraMindSimulator
```

## Test Scenarios

### SentinelUser (70% of traffic)
Simulates operators and automated systems:
- List workloads (10x weight)
- List deployments (8x weight)
- Query specific deployment (5x weight)
- Create workloads (3x weight)
- Submit action plans (2x weight)
- Query audits (4x weight)
- Health checks (6x weight)

### InfraMindSimulator (20% of traffic)
Simulates InfraMind Decision API:
- Batch action plan submissions every 10-30s
- Multiple decisions per plan (1-5 decisions)
- System-level authentication

### CanaryDeploymentUser (10% of traffic)
Simulates canary workflows:
- Create canary deployment
- Monitor progress
- Occasional rollbacks (10% of deployments)

## Performance Targets

From Phase 4 requirements:

| Metric | Target | Notes |
|--------|--------|-------|
| API p99 latency | <500ms | Under normal load |
| Plan submission | <30s | 99% of valid plans |
| Throughput | 100+ req/s | Sustained |
| Error rate | <0.1% | Excluding rate limits |
| Concurrent plans | 50+ | Simultaneous canaries |

## Test Profiles

### Smoke Test (Quick validation)
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=10 --spawn-rate=2 --run-time=1m --headless
```

### Load Test (Normal traffic)
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=100 --spawn-rate=10 --run-time=10m --headless
```

### Stress Test (2x peak traffic)
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=200 --spawn-rate=20 --run-time=30m --headless
```

### Spike Test (Sudden traffic surge)
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=500 --spawn-rate=100 --run-time=5m --headless
```

### Endurance Test (Sustained load)
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=100 --spawn-rate=10 --run-time=4h --headless
```

## Analyzing Results

Locust generates an HTML report with:
- Request statistics (RPS, response times, failure rate)
- Response time distribution
- Number of failures
- Charts over time

Key metrics to monitor:
- **95th/99th percentile latency** - Should stay under target
- **Failure rate** - Should be <0.1% (excluding 429 rate limits)
- **RPS** - Requests per second sustained
- **Median response time** - Should be <100ms for reads

## Running with Prometheus Monitoring

```bash
# Terminal 1: Start Prometheus
docker-compose -f deploy/docker-compose/docker-compose.yml up prometheus grafana

# Terminal 2: Start Control API
cd services/control-api && uvicorn app.main:app --port 8000

# Terminal 3: Run load test
locust -f tests/load/locustfile.py --host=http://localhost:8000 \
  --users=100 --spawn-rate=10 --run-time=10m

# Terminal 4: Watch metrics
open http://localhost:3000  # Grafana
# Dashboard: SRE Overview
# Watch: API latency, error rate, throughput
```

## CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Load Test
  run: |
    locust -f tests/load/locustfile.py \
      --host=http://api-staging:8000 \
      --users=50 \
      --spawn-rate=5 \
      --run-time=5m \
      --headless \
      --html=load-test-report.html \
      --csv=load-test

    # Check results meet SLO
    python scripts/check_load_test_results.py load-test_stats.csv
```

## Troubleshooting

### High Latency
- Check database connection pool
- Check Prometheus query performance
- Check Kafka consumer lag
- Scale Control API horizontally

### High Error Rate
- Check logs: `kubectl logs -l app=control-api --tail=100`
- Check policy violations blocking requests
- Check database is accessible
- Check rate limiter settings

### Rate Limiting (429 errors)
- This is expected under high load
- Adjust rate limits in policy engine
- Implement exponential backoff in clients

## Custom Scenarios

Create custom test scenarios by subclassing `HttpUser`:

```python
from locust import HttpUser, task, between

class CustomScenario(HttpUser):
    wait_time = between(1, 3)

    @task
    def my_workflow(self):
        # Your custom test logic
        self.client.get("/api/v1/custom-endpoint")
```

Run with: `locust -f my_test.py --user-classes CustomScenario`
