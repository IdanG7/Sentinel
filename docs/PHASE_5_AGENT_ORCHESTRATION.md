# Phase 5: Intelligent Agent Orchestration

## Overview

Phase 5 transforms Sentinel from an orchestration platform into an **AI-driven agent controller** that manages autonomous remediation modules, starting with PatchBot for automatic CI/CD failure resolution.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    InfraMind (Brain)                         │
│  Failure Prediction → Optimization → Outcome Learning        │
└────────────┬──────────────────────────┬─────────────────────┘
             │ Predictions              │ Outcomes
             ▼                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Sentinel (Executor)                       │
│                                                              │
│  Control API → Policy Engine → Pipeline Controller          │
│                                     │                        │
│                         ┌───────────▼───────────┐           │
│                         │  Agent Controller     │           │
│                         │  - Task Queue         │           │
│                         │  - Agent Registry     │           │
│                         │  - Task Monitoring    │           │
│                         └───────────┬───────────┘           │
│                                     │                        │
│                         ┌───────────▼───────────┐           │
│                         │  Failure Ingestion    │           │
│                         │  - GitHub Webhooks    │           │
│                         │  - GitLab Webhooks    │           │
│                         │  - Log Parsing        │           │
│                         └───────────────────────┘           │
└─────────────────────────────────────────────────────────────┘
             │                          │
             ▼                          ▼
┌──────────────────┐          ┌──────────────────┐
│  GitHub/GitLab   │          │   PatchBot       │
│  - CI/CD Logs    │◄─────────│   - Fix Gen      │
│  - PR Creation   │          │   - Validation   │
└──────────────────┘          └──────────────────┘
```

## Components

### 1. Agent Controller Service

**Location:** `services/agent-controller/`

**Purpose:** Central orchestration service for managing autonomous agents

**Key Features:**
- Agent registration and discovery
- Task queue management with priority
- Health monitoring and heartbeats
- Metrics collection and reporting
- Rate limiting and policy enforcement
- Correlation with InfraMind predictions

**API Endpoints:**
- `POST /api/v1/agents` - Register new agent
- `GET /api/v1/agents` - List all agents
- `GET /api/v1/agents/{id}` - Get agent details
- `PUT /api/v1/agents/{id}/heartbeat` - Update agent heartbeat
- `POST /api/v1/tasks` - Create new task
- `GET /api/v1/tasks/{id}` - Get task status
- `DELETE /api/v1/tasks/{id}` - Cancel task

**Database Tables:**
- `agents` - Agent registry with capabilities
- `agent_tasks` - Task queue and execution history
- `failure_fixes` - PatchBot-specific fix tracking
- `rate_limits` - Rate limiting enforcement

### 2. Failure Ingestion Service

**Location:** `services/failure-ingestion/`

**Purpose:** Receives CI/CD webhook events and creates agent tasks

**Key Features:**
- GitHub Actions webhook receiver
- GitLab CI webhook receiver
- Automatic failure classification
- Log parsing and error extraction
- Webhook signature validation
- Automatic task creation

**Webhook Endpoints:**
- `POST /webhooks/github/workflow_run` - GitHub workflow completions
- `POST /webhooks/github/workflow_job` - GitHub job completions
- `POST /webhooks/gitlab/pipeline` - GitLab pipeline completions
- `POST /webhooks/gitlab/job` - GitLab job completions

**Failure Types Detected:**
- Linting errors (ESLint, Pylint, etc.)
- Formatting issues (Prettier, Black, etc.)
- Type checking errors (TypeScript, mypy)
- Test failures
- Build errors
- Dependency issues

### 3. Agent SDK

**Location:** `libs/agent-sdk/`

**Purpose:** Standard interface for building autonomous agents

**Key Classes:**
```python
from agent_sdk import (
    AgentClient,
    AgentCapabilities,
    AgentTask,
    TaskResult,
)

# Define capabilities
capabilities = AgentCapabilities(
    supported_tasks=["ci_failure_fix"],
    max_concurrent_tasks=3,
    timeout_seconds=1800,
)

# Create client
client = AgentClient(
    agent_name="my-agent",
    version="1.0.0",
    capabilities=capabilities,
    controller_url="http://agent-controller:8003",
)

# Register task handler
async def handle_task(task: AgentTask) -> TaskResult:
    # Process task
    return TaskResult(success=True, data={...})

client.register_task_handler("ci_failure_fix", handle_task)

# Run agent
async with client:
    await client.run()
```

**Features:**
- Automatic registration with Agent Controller
- Task polling and execution
- Progress reporting
- Heartbeat management
- Graceful shutdown
- Error handling and retry logic

### 4. PatchBot Agent

**Location:** `agents/patchbot/`

**Purpose:** Autonomous CI/CD failure resolution agent

**Capabilities:**
- Analyzes CI/CD failure logs
- Classifies failure types
- Generates code fixes using AI (Claude/GPT)
- Validates fixes in sandbox (optional)
- Creates pull requests automatically
- Tracks fix outcomes

**Supported Failure Types:**
- Linting errors
- Formatting issues
- Type checking errors
- Simple test failures
- Import errors
- Deprecated API usage

**Configuration:**
```bash
# Required
ANTHROPIC_API_KEY=sk-...
GITHUB_TOKEN=ghp_...

# Optional
CONTROLLER_URL=http://agent-controller:8003
AUTO_MERGE_CONFIDENCE_THRESHOLD=0.9
CREATE_BRANCH=true
OPEN_PR=true
SANDBOX_ENABLED=false
```

**Workflow:**
1. Receive failure task from Agent Controller
2. Clone repository to temporary workspace
3. Analyze logs and classify failure
4. Read affected files
5. Generate fix using LLM
6. Apply changes and create branch
7. Commit changes
8. Create pull request (optional)
9. Report results back to Agent Controller

## Deployment

### Docker Compose

The Phase 5 components are included in the main `docker-compose.yml`:

```yaml
services:
  agent-controller:
    build: ./services/agent-controller
    ports:
      - "8003:8003"
    environment:
      DATABASE_URL: postgresql+asyncpg://sentinel:sentinel@postgres:5432/sentinel
      REDIS_URL: redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  failure-ingestion:
    build: ./services/failure-ingestion
    ports:
      - "8004:8004"
    environment:
      AGENT_CONTROLLER_URL: http://agent-controller:8003
    depends_on:
      - agent-controller
```

Start services:
```bash
docker-compose up -d agent-controller failure-ingestion
```

### Running PatchBot

PatchBot runs as a separate agent process:

```bash
cd agents/patchbot
pip install -e .

# Set environment variables
export ANTHROPIC_API_KEY=sk-...
export GITHUB_TOKEN=ghp_...
export CONTROLLER_URL=http://localhost:8003

# Run agent
python -m patchbot.agent
```

Or with Docker:
```bash
cd agents/patchbot
docker build -t sentinel-patchbot .
docker run -e ANTHROPIC_API_KEY=sk-... \
           -e GITHUB_TOKEN=ghp_... \
           -e CONTROLLER_URL=http://agent-controller:8003 \
           sentinel-patchbot
```

## Webhook Setup

### GitHub Actions

1. Go to repository settings → Webhooks → Add webhook
2. Payload URL: `https://your-domain.com/webhooks/github/workflow_run`
3. Content type: `application/json`
4. Secret: Set `GITHUB_WEBHOOK_SECRET` in environment
5. Events: Select "Workflow runs"

### GitLab CI

1. Go to project settings → Webhooks
2. URL: `https://your-domain.com/webhooks/gitlab/pipeline`
3. Secret token: Set `GITLAB_WEBHOOK_SECRET` in environment
4. Trigger: "Pipeline events"

## Safety & Policies

### Rate Limiting

Prevents spam and runaway automation:

```python
rate_limits:
  max_fixes_per_hour: 10
  max_fixes_per_day: 50
  max_fixes_per_repo: 5
  cooldown_after_failure_minutes: 60
```

### Confidence Thresholds

Controls when fixes are auto-merged:

```python
confidence_thresholds:
  auto_merge_threshold: 0.9
  auto_create_pr_threshold: 0.7
  require_review_below: 0.7
```

### Blast Radius Control

Limits concurrent operations:

```python
blast_radius:
  max_concurrent_fixes: 3
  max_repos_affected_simultaneously: 10
```

## Metrics & Monitoring

### Agent Controller Metrics

- `agent_controller_agents_total` - Total registered agents
- `agent_controller_agents_active` - Currently active agents
- `agent_controller_tasks_created` - Tasks created
- `agent_controller_tasks_completed` - Tasks completed
- `agent_controller_tasks_failed` - Tasks failed
- `agent_controller_task_duration_seconds` - Task execution time

### PatchBot Metrics

- `patchbot_fixes_generated` - Total fixes generated
- `patchbot_fixes_successful` - Successful fixes
- `patchbot_fixes_failed` - Failed fixes
- `patchbot_pr_created` - PRs created
- `patchbot_pr_merged` - PRs merged
- `patchbot_fix_confidence` - Average fix confidence
- `patchbot_time_to_fix_seconds` - Time to generate fix

## Testing

Run tests for Agent Controller:
```bash
cd services/agent-controller
pytest tests/ -v
```

Run tests for Failure Ingestion:
```bash
cd services/failure-ingestion
pytest tests/ -v
```

Run tests for PatchBot:
```bash
cd agents/patchbot
pytest tests/ -v
```

## Troubleshooting

### Agent Not Registering

Check Agent Controller logs:
```bash
docker logs sentinel-agent-controller
```

Verify agent configuration and controller URL.

### Tasks Not Being Created

Check Failure Ingestion logs:
```bash
docker logs sentinel-failure-ingestion
```

Verify webhook secrets and CI/CD event payloads.

### PatchBot Not Generating Fixes

Check:
1. `ANTHROPIC_API_KEY` is valid
2. API rate limits not exceeded
3. Task timeout is sufficient (1800s default)
4. Agent Controller is reachable

### PRs Not Being Created

Check:
1. `GITHUB_TOKEN` has required permissions
2. `OPEN_PR=true` in configuration
3. Repository allows PR creation from token

## Next Steps

See `PHASE_5_PLAN.md` for:
- Additional agent types (LogAnalyzer, ConfigOptimizer)
- Enhanced validation sandbox
- Multi-tenancy support
- Cost optimization strategies

## References

- [Agent SDK Documentation](../libs/agent-sdk/README.md)
- [PatchBot Documentation](../agents/patchbot/README.md)
- [API Reference](./API_REFERENCE.md)
