# Agent Controller

Orchestration service for autonomous AI agents in Sentinel.

## Overview

The Agent Controller manages the lifecycle of AI agents (like PatchBot) that perform automated remediation tasks. It provides:

- **Agent Registry**: Register and discover available agents
- **Task Queue**: Queue and prioritize agent tasks
- **Execution Management**: Sandboxed execution with monitoring
- **Policy Enforcement**: Rate limits and safety guardrails
- **Telemetry**: Correlation with InfraMind predictions

## Architecture

```
┌──────────────────────────────────────────────┐
│          Agent Controller                     │
│                                               │
│  ┌─────────────┐       ┌──────────────┐     │
│  │   Registry  │       │  Task Queue  │     │
│  └──────┬──────┘       └──────┬───────┘     │
│         │                     │              │
│  ┌──────▼──────────────────────▼───────┐    │
│  │      Execution Manager              │    │
│  │  - Sandboxing                        │    │
│  │  - Resource limits                   │    │
│  │  - Health monitoring                 │    │
│  └──────┬──────────────────────────────┘    │
│         │                                    │
│  ┌──────▼──────────┐                        │
│  │  Policy Engine  │                        │
│  └─────────────────┘                        │
└──────────────────────────────────────────────┘
         │                │
         ▼                ▼
   ┌─────────┐      ┌──────────┐
   │ PatchBot│      │ Future   │
   │  Agent  │      │  Agents  │
   └─────────┘      └──────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run service
uvicorn app.main:app --reload --port 8082

# Register an agent
curl -X POST http://localhost:8082/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "patchbot",
    "version": "1.0.0",
    "capabilities": {
      "fix_types": ["linting", "formatting", "imports"],
      "max_concurrent_tasks": 5
    }
  }'

# Submit a task
curl -X POST http://localhost:8082/api/v1/agents/patchbot/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "fix_ci_failure",
    "context": {
      "repo": "org/repo",
      "error": "ESLint: x is not defined",
      "logs": "..."
    }
  }'

# Check task status
curl http://localhost:8082/api/v1/tasks/{task_id}
```

## Agent Development

See `libs/agent-sdk/` for developing custom agents.

Example agent:

```python
from agent_sdk import Agent, AgentTask, AgentResult

class MyAgent(Agent):
    async def initialize(self, config):
        self.config = config

    async def execute(self, task: AgentTask) -> AgentResult:
        # Your agent logic here
        return AgentResult(
            task_id=task.id,
            status='completed',
            artifacts=[...],
            metrics={...}
        )

    async def cleanup(self):
        # Cleanup resources
        pass

    def get_capabilities(self):
        return {
            "supported_tasks": ["my_task_type"],
            "max_concurrent": 3
        }
```

## Configuration

Environment variables:

```bash
# Service
AGENT_CONTROLLER_PORT=8082
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql://user:pass@localhost/sentinel

# Redis (task queue)
REDIS_URL=redis://localhost:6379

# Sandboxing
SANDBOX_ENABLED=true
SANDBOX_TIMEOUT_SECONDS=600
SANDBOX_MEMORY_LIMIT_MB=2048

# Policy
MAX_CONCURRENT_TASKS=10
RATE_LIMIT_PER_HOUR=50
```

## API Reference

See OpenAPI docs at http://localhost:8082/docs

## Monitoring

Metrics exposed at `/metrics`:

- `agent_controller_agents_total` - Total registered agents
- `agent_controller_tasks_total{status}` - Tasks by status
- `agent_controller_task_duration_seconds` - Task execution time
- `agent_controller_agent_health_score{agent}` - Agent health (0-1)

## Testing

```bash
# Run tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Integration tests
pytest tests/integration/ -v
```
