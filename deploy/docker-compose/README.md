# Sentinel Local Development Environment

This Docker Compose setup provides a complete local development environment for Sentinel.

## Services Included

| Service | Port | Description |
|---------|------|-------------|
| **Prometheus** | 9090 | Metrics collection and querying |
| **Alertmanager** | 9093 | Alert management |
| **Grafana** | 3000 | Metrics visualization and dashboards |
| **Kafka** | 9092, 9094 | Event streaming |
| **Kafka UI** | 8080 | Web UI for Kafka |
| **Zookeeper** | 2181 | Kafka coordination |
| **Vault** | 8200 | Secrets management |
| **PostgreSQL** | 5432 | Database for Control API |
| **MLflow** | 5000 | Experiment tracking |
| **Jaeger** | 16686 | Distributed tracing |

## Quick Start

### 1. Start All Services

```bash
# From the project root
make dev-up

# Or directly
cd deploy/docker-compose
docker compose up -d
```

### 2. Verify Services are Running

```bash
docker compose ps
```

All services should show `Up` status.

### 3. Access Web UIs

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/sentinel)
- **Kafka UI**: http://localhost:8080
- **Vault**: http://localhost:8200 (token: sentinel-dev-token)
- **MLflow**: http://localhost:5000
- **Jaeger**: http://localhost:16686
- **Alertmanager**: http://localhost:9093

## Service Configuration

### Grafana

- **Username**: admin
- **Password**: sentinel
- Pre-configured datasource: Prometheus
- Pre-loaded dashboard: Sentinel SRE Overview

### Vault

- **Dev Mode**: Yes (DO NOT use in production)
- **Root Token**: sentinel-dev-token
- **Endpoint**: http://localhost:8200

To access Vault CLI:
```bash
export VAULT_ADDR=http://localhost:8200
export VAULT_TOKEN=sentinel-dev-token
vault status
```

### PostgreSQL

- **Database**: sentinel
- **Username**: sentinel
- **Password**: sentinel
- **Port**: 5432

Connect with psql:
```bash
psql -h localhost -U sentinel -d sentinel
```

### Kafka

- **Internal**: kafka:9092 (from containers)
- **External**: localhost:9094 (from host)

Create topic:
```bash
docker exec -it sentinel-kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic sentinel.events \
  --partitions 3 \
  --replication-factor 1
```

## Kafka Topics

The following topics are auto-created by Sentinel services:

- `sentinel.events` - General platform events
- `sentinel.deployments` - Deployment lifecycle events
- `sentinel.anomalies` - Anomaly detection events
- `sentinel.policy.violations` - Policy violation events
- `sentinel.telemetry` - Telemetry data stream

## Viewing Logs

```bash
# All services
make dev-logs

# Specific service
docker compose logs -f prometheus
docker compose logs -f grafana
```

## Stopping Services

```bash
# Stop all services
make dev-down

# Or
docker compose down

# Stop and remove volumes (WARNING: deletes all data)
docker compose down -v
```

## Troubleshooting

### Prometheus Not Scraping Sentinel Services

Sentinel services run on the host (not in Docker), so Prometheus needs to reach `host.docker.internal`.

**On Linux**, add to `/etc/hosts`:
```
127.0.0.1 host.docker.internal
```

Or update `prometheus/prometheus.yml` to use `172.17.0.1` (Docker bridge IP).

### Grafana Dashboard Not Loading

1. Check datasource configuration:
   - Go to Configuration → Data Sources
   - Verify Prometheus URL: `http://prometheus:9090`
   - Click "Save & Test"

2. Reload dashboard:
   - Go to Dashboards → Browse
   - Find "Sentinel - SRE Overview"

### Kafka Connection Issues

Check Kafka is healthy:
```bash
docker exec -it sentinel-kafka kafka-broker-api-versions \
  --bootstrap-server localhost:9092
```

### Vault Sealed

Vault in dev mode should auto-unseal. If sealed:
```bash
docker compose restart vault
```

### PostgreSQL Connection Refused

Wait for PostgreSQL to fully start:
```bash
docker compose logs postgres | grep "ready to accept connections"
```

### Port Conflicts

If ports are already in use, modify `docker-compose.yml` to use different ports:

```yaml
services:
  grafana:
    ports:
      - "3001:3000"  # Use 3001 instead of 3000
```

## Data Persistence

Data is persisted in Docker volumes:

```bash
# List volumes
docker volume ls | grep sentinel

# Inspect volume
docker volume inspect sentinel-dev_prometheus-data

# Backup volume
docker run --rm -v sentinel-dev_prometheus-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/prometheus-backup.tar.gz /data
```

## Cleaning Up

### Remove All Containers and Volumes

```bash
docker compose down -v
```

### Remove Individual Volumes

```bash
docker volume rm sentinel-dev_prometheus-data
docker volume rm sentinel-dev_grafana-data
docker volume rm sentinel-dev_kafka-data
# ... etc
```

## Integration with Sentinel Services

### Control API

The Control API expects PostgreSQL connection:

```yaml
# services/control-api/config.yaml
database:
  url: postgresql://sentinel:sentinel@localhost:5432/sentinel
```

### InfraMind Adapter

The adapter expects Kafka and Prometheus:

```yaml
# services/infra-adapter/config.yaml
kafka:
  bootstrap_servers: localhost:9094
prometheus:
  url: http://localhost:9090
```

### Pipeline Controller

Needs Vault for kubeconfig secrets:

```yaml
# services/pipeline-controller/config.yaml
vault:
  address: http://localhost:8200
  token: sentinel-dev-token
```

## Development Workflow

1. Start dev environment:
   ```bash
   make dev-up
   ```

2. Run Sentinel services locally (from their directories):
   ```bash
   # Terminal 1: Control API
   cd services/control-api
   uvicorn app.main:app --reload --port 8000

   # Terminal 2: Pipeline Controller
   cd services/pipeline-controller
   python -m app.main

   # Terminal 3: Agent
   cd services/agent
   go run cmd/agent/main.go
   ```

3. View metrics in Prometheus: http://localhost:9090
4. View dashboards in Grafana: http://localhost:3000
5. Check events in Kafka UI: http://localhost:8080

## Next Steps

- Read [Development Guide](../../docs/guides/development.md)
- Check [Architecture Documentation](../../docs/architecture/README.md)
- Review [API Reference](../../docs/api/openapi.yaml)
