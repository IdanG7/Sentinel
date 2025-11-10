# Pipeline Controller

Orchestration engine for workload lifecycle management.

## Responsibilities

- Reconcile desired state with actual cluster state
- Execute deployments, scaling, rollbacks
- Implement rollout strategies (canary, blue/green)
- Health checks and validation
- Idempotent operation execution

## Components

- **Reconciliation Loop:** Watches cluster state and converges to desired
- **Rollout Engine:** Manages staged deployments
- **Health Checker:** Validates workload health during changes
- **Action Executor:** Applies validated action plans

## Development

```bash
cd services/pipeline-controller
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Configuration

- Cluster credentials from Vault
- Reconciliation interval (default: 30s)
- Rollout step delays and thresholds

## Testing

```bash
pytest tests/ -v --cov=app
```
