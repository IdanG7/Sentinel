# Phase 5: Intelligent Agent Orchestration (PatchBot Integration)

## Executive Summary

**Goal:** Transform Sentinel from an orchestration platform into an **AI-driven agent controller** that manages autonomous remediation modules, starting with PatchBot for automatic CI/CD failure resolution.

**Timeline:** Weeks 11-13 (3 weeks)

**Key Innovation:** Sentinel detects recurring failures and invokes specialized AI agents (starting with PatchBot) to fix them automatically, creating a self-healing development pipeline.

## Architecture Overview

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
│                         │  - Sandboxing         │           │
│                         │  - Monitoring         │           │
│                         └───────────┬───────────┘           │
│                                     │                        │
│                         ┌───────────▼───────────┐           │
│                         │   Agent Registry      │           │
│                         │   - PatchBot          │ ← Phase 5 │
│                         │   - LogAnalyzer       │ ← Future  │
│                         │   - ConfigOptimizer   │ ← Future  │
│                         └───────────┬───────────┘           │
│                                     │                        │
│                         ┌───────────▼───────────┐           │
│                         │  Execution Sandbox    │           │
│                         │  (Docker/gVisor)      │           │
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

## Week 1: Agent Controller Foundation

### 1.1 Agent Controller Service

**Location:** `services/agent-controller/`

**Components:**
- Agent registry (database-backed)
- Task queue (Redis or in-memory)
- Lifecycle management (start, stop, pause, resume)
- Health monitoring
- Metrics collection

**Key Features:**
- Register agents with capabilities
- Queue tasks with priority
- Sandboxed execution
- Result aggregation
- Failure retry with backoff

**Database Schema:**
```sql
CREATE TABLE agents (
  id UUID PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  version VARCHAR(20) NOT NULL,
  capabilities JSONB NOT NULL,
  status VARCHAR(20) NOT NULL,  -- active, paused, failed
  health_score FLOAT DEFAULT 1.0,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE TABLE agent_tasks (
  id UUID PRIMARY KEY,
  agent_id UUID REFERENCES agents(id),
  task_type VARCHAR(50) NOT NULL,
  context JSONB NOT NULL,
  status VARCHAR(20) NOT NULL,  -- pending, running, completed, failed
  result JSONB,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  duration_ms INTEGER,
  correlation_id UUID  -- Link to InfraMind prediction
);

CREATE TABLE failure_fixes (
  id UUID PRIMARY KEY,
  failure_signature VARCHAR(255) NOT NULL,
  repository VARCHAR(255) NOT NULL,
  failure_type VARCHAR(50) NOT NULL,
  agent_task_id UUID REFERENCES agent_tasks(id),
  fix_pr_url VARCHAR(500),
  fix_confidence FLOAT,
  fix_success BOOLEAN,
  time_to_fix_seconds INTEGER,
  created_at TIMESTAMP
);
```

**API Endpoints:**
- `POST /api/v1/agents` - Register new agent
- `GET /api/v1/agents` - List all agents
- `GET /api/v1/agents/{id}` - Get agent details
- `POST /api/v1/agents/{id}/tasks` - Submit task to agent
- `GET /api/v1/tasks/{id}` - Get task status
- `DELETE /api/v1/tasks/{id}` - Cancel task

### 1.2 Agent SDK

**Location:** `libs/agent-sdk/`

**Purpose:** Standard interface for building agents

**Key Interfaces:**
```python
from abc import ABC, abstractmethod
from typing import Any, Dict

class Agent(ABC):
    """Base class for all agents."""

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize agent with configuration."""
        pass

    @abstractmethod
    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute a task and return result."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities."""
        pass

class AgentTask:
    """Task to be executed by agent."""
    id: str
    task_type: str
    context: Dict[str, Any]
    payload: bytes
    timeout_seconds: int

class AgentResult:
    """Result of agent execution."""
    task_id: str
    status: str  # completed, failed, partial
    progress: float  # 0.0 to 1.0
    artifacts: List[Artifact]  # Generated files, PRs, logs
    metrics: Dict[str, float]
    error_message: Optional[str]
```

**Built-in Features:**
- Automatic telemetry collection
- Structured logging
- Health checks
- Graceful shutdown
- Resource limits

### 1.3 Policy Extensions

**New Policies for Auto-Remediation:**

```python
class AutoRemediationPolicy:
    """Policy for safe auto-remediation."""

    rate_limits: RateLimits
    confidence_thresholds: ConfidenceThresholds
    blast_radius: BlastRadiusControl
    review_gates: ReviewGates
    rollback_rules: RollbackRules

class RateLimits:
    max_fixes_per_hour: int = 10
    max_fixes_per_day: int = 50
    max_fixes_per_repo: int = 5
    cooldown_after_failure_minutes: int = 60

class ConfidenceThresholds:
    auto_merge_threshold: float = 0.9
    auto_create_pr_threshold: float = 0.7
    require_review_below: float = 0.7

class BlastRadiusControl:
    max_concurrent_fixes: int = 3
    max_repos_affected_simultaneously: int = 10

class ReviewGates:
    require_review_for_security_changes: bool = True
    require_review_for_production_configs: bool = True
    escalation_timeout_hours: int = 24
```

## Week 2: PatchBot Agent Implementation

### 2.1 PatchBot Agent

**Location:** `agents/patchbot/`

**Responsibilities:**
- Analyze CI/CD failure logs
- Generate code fixes
- Validate fixes in sandbox
- Create pull requests
- Track PR lifecycle

**Core Components:**

```python
class PatchBot(Agent):
    """Agent that fixes CI/CD failures automatically."""

    def __init__(self):
        self.llm_client = OpenAIClient()  # or Anthropic, etc.
        self.git_client = GitHubClient()
        self.sandbox = ValidationSandbox()

    async def execute(self, task: AgentTask) -> AgentResult:
        """
        Execute fix generation workflow.

        1. Parse failure logs
        2. Classify failure type
        3. Generate fix candidates
        4. Validate in sandbox
        5. Create PR
        6. Monitor PR status
        """
        failure_context = task.context

        # Step 1: Parse and classify
        failure_type = await self.classify_failure(
            logs=failure_context['logs'],
            error_message=failure_context['error']
        )

        # Step 2: Generate fix
        fix_candidates = await self.generate_fixes(
            failure_type=failure_type,
            repository=failure_context['repo'],
            branch=failure_context['branch'],
            error_context=failure_context
        )

        # Step 3: Validate
        best_fix = await self.validate_fixes(
            candidates=fix_candidates,
            repository=failure_context['repo']
        )

        if not best_fix:
            return AgentResult(
                task_id=task.id,
                status='failed',
                error_message='No valid fix found'
            )

        # Step 4: Create PR
        pr_url = await self.create_pull_request(
            repository=failure_context['repo'],
            fix=best_fix,
            failure_context=failure_context
        )

        return AgentResult(
            task_id=task.id,
            status='completed',
            artifacts=[
                Artifact(type='pull_request', url=pr_url),
                Artifact(type='fix_diff', content=best_fix.diff)
            ],
            metrics={
                'confidence': best_fix.confidence,
                'time_to_fix_seconds': ...
            }
        )

    async def classify_failure(self, logs: str, error_message: str) -> FailureType:
        """Classify failure using pattern matching + LLM."""
        # Check known patterns first
        for pattern in KNOWN_FAILURE_PATTERNS:
            if pattern.matches(error_message):
                return pattern.failure_type

        # Use LLM for unknown patterns
        prompt = f"""
        Classify this CI/CD failure:

        Error: {error_message}
        Logs: {logs[:2000]}

        Categories: linting, test_failure, build_error, dependency_issue, deployment_failure

        Return JSON: {{"type": "...", "confidence": 0.0-1.0, "reason": "..."}}
        """

        response = await self.llm_client.complete(prompt)
        return FailureType.from_json(response)

    async def generate_fixes(
        self,
        failure_type: FailureType,
        repository: str,
        branch: str,
        error_context: dict
    ) -> List[FixCandidate]:
        """Generate multiple fix candidates using LLM."""
        # Fetch relevant code
        affected_files = self.extract_affected_files(error_context)
        code_context = await self.git_client.get_files(repository, affected_files)

        prompt = f"""
        Generate a fix for this {failure_type} failure:

        Error: {error_context['error']}
        Stack trace: {error_context.get('stack_trace', '')}

        Affected files:
        {code_context}

        Generate 3 fix candidates in order of confidence.
        Return JSON array with: {{"file": "...", "changes": [...], "confidence": 0.0-1.0, "explanation": "..."}}
        """

        response = await self.llm_client.complete(prompt)
        return [FixCandidate.from_json(c) for c in response]

    async def validate_fixes(
        self,
        candidates: List[FixCandidate],
        repository: str
    ) -> Optional[FixCandidate]:
        """Validate fixes in isolated sandbox."""
        for candidate in sorted(candidates, key=lambda x: x.confidence, reverse=True):
            try:
                # Apply fix in sandbox
                await self.sandbox.apply_changes(candidate.changes)

                # Run tests
                test_result = await self.sandbox.run_tests()

                if test_result.success:
                    logger.info(f"✓ Fix validated: {candidate.explanation}")
                    return candidate

            except Exception as e:
                logger.warning(f"Fix validation failed: {e}")
                continue

        return None

    async def create_pull_request(
        self,
        repository: str,
        fix: FixCandidate,
        failure_context: dict
    ) -> str:
        """Create PR with fix."""
        branch_name = f"fix/ci-failure-{uuid.uuid4().hex[:8]}"

        # Create branch and push changes
        await self.git_client.create_branch(repository, branch_name)
        await self.git_client.commit_changes(
            repository=repository,
            branch=branch_name,
            changes=fix.changes,
            message=f"Fix: {failure_context['error'][:50]}\n\nGenerated by PatchBot"
        )

        # Create PR
        pr = await self.git_client.create_pr(
            repository=repository,
            head=branch_name,
            base='main',
            title=f"Fix CI failure: {failure_context['error'][:80]}",
            body=self.generate_pr_description(fix, failure_context)
        )

        return pr.url

    def generate_pr_description(self, fix: FixCandidate, failure_context: dict) -> str:
        """Generate PR description with context."""
        return f"""
## 🤖 Automated Fix by PatchBot

### Failure Details
- **Type:** {failure_context['failure_type']}
- **Error:** `{failure_context['error']}`
- **Build:** {failure_context.get('build_url', 'N/A')}
- **Detected:** {failure_context['timestamp']}

### Fix Applied
{fix.explanation}

**Confidence:** {fix.confidence:.0%}

### Changes
```diff
{fix.diff}
```

### Validation
✓ Tests passed in sandbox environment

### Links
- [Original failure logs]({failure_context.get('build_url')})
- [InfraMind analysis]({failure_context.get('inframind_url')})

---
Generated by [Sentinel PatchBot](https://github.com/org/sentinel)
"""
```

### 2.2 Failure Types & Patterns

```python
class FailureType(Enum):
    """Types of CI/CD failures PatchBot can handle."""

    LINTING = "linting"  # ESLint, Pylint, etc.
    FORMATTING = "formatting"  # Prettier, Black, etc.
    TYPE_CHECKING = "type_checking"  # TypeScript, mypy
    TEST_FAILURE = "test_failure"  # Unit/integration tests
    BUILD_ERROR = "build_error"  # Compilation errors
    DEPENDENCY_ISSUE = "dependency_issue"  # Package conflicts
    IMPORT_ERROR = "import_error"  # Missing imports
    DEPRECATION = "deprecation"  # Deprecated API usage

KNOWN_FAILURE_PATTERNS = [
    FailurePattern(
        pattern=r"ESLint: .* is not defined",
        failure_type=FailureType.LINTING,
        fix_strategy="add_eslint_global"
    ),
    FailurePattern(
        pattern=r"Black would reformat",
        failure_type=FailureType.FORMATTING,
        fix_strategy="run_black_formatter"
    ),
    FailurePattern(
        pattern=r"ModuleNotFoundError: No module named '(.*)'",
        failure_type=FailureType.IMPORT_ERROR,
        fix_strategy="add_import_or_dependency"
    ),
    # ... more patterns
]
```

## Week 3: Integration & Testing

### 3.1 Failure Ingestion Pipeline

**Location:** `services/agent-controller/app/ingestion/`

**Components:**
- CI/CD webhook receivers (GitHub Actions, GitLab CI, Jenkins)
- Log parser and normalizer
- Failure classifier
- Task creator

**Flow:**
```python
@app.post("/webhooks/github/workflow")
async def github_workflow_webhook(request: Request):
    """Receive GitHub Actions workflow events."""
    payload = await request.json()

    if payload['action'] == 'completed' and payload['workflow_run']['conclusion'] == 'failure':
        # Fetch logs
        logs = await fetch_workflow_logs(payload['workflow_run']['logs_url'])

        # Parse and classify
        failure = parse_github_logs(logs)

        # Create agent task
        task = AgentTask(
            agent_id='patchbot',
            task_type='fix_ci_failure',
            context={
                'repo': payload['repository']['full_name'],
                'branch': payload['workflow_run']['head_branch'],
                'error': failure.error_message,
                'logs': logs,
                'build_url': payload['workflow_run']['html_url'],
                'timestamp': payload['workflow_run']['updated_at']
            }
        )

        # Submit to agent controller
        result = await agent_controller.submit_task(task)

        return {'task_id': result.task_id}
```

### 3.2 Telemetry Correlation

**Link InfraMind predictions → Agent outcomes:**

```python
class TelemetryCorrelator:
    """Correlate InfraMind predictions with agent outcomes."""

    async def correlate_prediction_to_outcome(
        self,
        prediction_id: str,
        agent_task_id: str
    ):
        """Link InfraMind prediction to agent task."""
        await db.execute("""
            UPDATE agent_tasks
            SET correlation_id = :prediction_id
            WHERE id = :agent_task_id
        """, {'prediction_id': prediction_id, 'agent_task_id': agent_task_id})

    async def send_outcome_to_inframind(
        self,
        task_id: str,
        result: AgentResult
    ):
        """Send agent outcome back to InfraMind for learning."""
        task = await db.get_task(task_id)

        outcome = {
            'prediction_id': task.correlation_id,
            'agent': 'patchbot',
            'success': result.status == 'completed',
            'confidence': result.metrics.get('confidence'),
            'time_to_fix_seconds': result.metrics.get('time_to_fix_seconds'),
            'failure_type': task.context['failure_type'],
            'repository': task.context['repo']
        }

        # Send to InfraMind via gRPC
        await inframind_client.report_agent_outcome(outcome)
```

### 3.3 Testing Strategy

**Unit Tests:**
- Agent registration and lifecycle
- Task queuing and execution
- PatchBot fix generation
- Failure classification
- Policy enforcement

**Integration Tests:**
- End-to-end: Webhook → Fix → PR
- GitHub Actions integration
- Sandbox validation
- InfraMind correlation

**Test Scenarios:**
```python
async def test_patchbot_fixes_linting_error():
    """Test PatchBot fixes ESLint error."""
    # Arrange
    failure = create_test_failure(
        type='linting',
        error='ESLint: x is not defined',
        repo='test/repo'
    )

    # Act
    task = await agent_controller.submit_task(failure)
    result = await wait_for_task_completion(task.id, timeout=300)

    # Assert
    assert result.status == 'completed'
    assert result.artifacts[0].type == 'pull_request'
    assert result.metrics['confidence'] > 0.8

async def test_patchbot_respects_rate_limits():
    """Test rate limiting prevents spam."""
    # Submit 20 tasks quickly
    tasks = [await submit_fix_task() for _ in range(20)]

    # Only first 10 should execute (rate limit)
    completed = [t for t in tasks if t.status == 'completed']
    rate_limited = [t for t in tasks if t.status == 'rate_limited']

    assert len(completed) == 10
    assert len(rate_limited) == 10
```

## Success Criteria

- ✅ Agent Controller operational with agent registry
- ✅ PatchBot successfully fixes 3+ failure types (linting, formatting, imports)
- ✅ 70%+ fix success rate on test cases
- ✅ Average time-to-PR < 5 minutes
- ✅ Zero unauthorized actions (all policy-compliant)
- ✅ Rate limiting prevents spam
- ✅ Telemetry correlation functional
- ✅ Human review workflow for low-confidence fixes

## Deliverables

1. **Agent Controller Service** (`services/agent-controller/`)
2. **Agent SDK** (`libs/agent-sdk/`)
3. **PatchBot Agent** (`agents/patchbot/`)
4. **Failure Ingestion Pipeline** (webhook receivers)
5. **Policy Extensions** (auto-remediation policies)
6. **Database Schema** (agents, tasks, fixes)
7. **Documentation** (agent dev guide, PatchBot manual)
8. **Tests** (unit + integration, 80%+ coverage)
9. **Grafana Dashboards** (agent metrics, fix success rates)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent generates breaking changes | High | Sandbox validation, confidence thresholds, mandatory review |
| Agent overwhelms repos with PRs | Medium | Rate limiting, cooldown periods, blast radius control |
| Security vulnerabilities in agent code | High | Isolated execution, restricted permissions, regular audits |
| InfraMind predictions inaccurate | Medium | Feedback loop to improve models, human review gates |
| LLM API costs too high | Medium | Local models fallback, caching, rate limiting |

## Next Steps After Phase 5

**Phase 6: Multi-Tenancy & Federation**
- Tenant isolation in agent controller
- Per-tenant rate limits and policies
- Cost allocation for agent execution

**Phase 7: Additional Agents**
- LogAnalyzer: Pattern detection in logs
- ConfigOptimizer: Auto-tune configs
- SecurityScanner: Vulnerability fixes
- PerformanceOptimizer: Code optimization suggestions

---

**Ready to build the future of self-healing infrastructure!** 🤖
