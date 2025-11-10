# Control API

FastAPI-based REST API for Sentinel operations.

## Responsibilities

- Workload registration and deployment management
- Policy CRUD operations
- Action plan submission and validation
- Audit log queries
- Authentication (JWT) and authorization (RBAC)

## Endpoints

See [API spec](../../docs/api/openapi.yaml) for full reference.

Key routes:
- `POST /v1/workloads` - Register workload
- `POST /v1/deployments` - Deploy to cluster
- `POST /v1/deployments/{id}/scale` - Scale workload
- `POST /v1/policies` - Create policy set
- `POST /v1/action-plans` - Submit action plan
- `GET /v1/audits` - Query audit logs

## Development

```bash
cd services/control-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Configuration

Reads from `CONFIG_PATH` (default: `config.yaml`).
Secrets loaded from environment or Vault.

## Testing

```bash
pytest tests/ -v --cov=app
```
