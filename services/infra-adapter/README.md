# InfraMind Adapter

gRPC bridge between Sentinel and InfraMind.

## Responsibilities

- Collect and batch telemetry from Sentinel components
- Stream telemetry to InfraMind's Telemetry Ingestor
- Receive action plans from InfraMind Decision API
- Validate and forward plans to Pipeline Controller
- Track plan acknowledgments and outcomes

## Architecture

```
Prometheus/Kafka → Adapter → [gRPC] → InfraMind
                      ↓
              Pipeline Controller
```

## Development

```bash
cd services/infra-adapter
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Configuration

- InfraMind endpoint: `INFRAMIND_GRPC_ENDPOINT`
- Telemetry batch size and interval
- gRPC TLS certificates

## Testing

```bash
pytest tests/ -v --cov=app
# Integration tests require InfraMind mock server
docker compose -f tests/docker-compose.test.yml up -d
pytest tests/integration/ -v
```
