# PatchBot Testing Guide

This guide shows you how to test PatchBot with Sentinel's own CI/CD pipeline.

## Prerequisites

- Docker and Docker Compose installed
- GitHub repository with Actions enabled
- (Optional) GitHub Personal Access Token for creating PRs
- (Optional) Anthropic API key for AI-powered fixes

## Quick Start (Local Testing)

### 1. Start Sentinel Services

```bash
# Start required services
docker-compose up -d postgres redis agent-controller failure-ingestion

# Check services are healthy
curl http://localhost:8003/health  # Agent Controller
curl http://localhost:8004/health  # Failure Ingestion
```

### 2. Run the Test Script

```bash
# Run end-to-end test
./scripts/test-patchbot.sh
```

This script will:
1. Verify services are running
2. Simulate a CI/CD failure webhook
3. Create a task in Agent Controller
4. Monitor task execution
5. Show results

### 3. Expected Output

```
🤖 PatchBot End-to-End Test Script
====================================

Step 1: Checking prerequisites...
✓ Prerequisites OK

Step 2: Starting Sentinel services...
✓ Services started

Step 3: Checking service health...
✓ Agent Controller is healthy
✓ Failure Ingestion is healthy

Step 4: Simulating CI/CD failure...
✓ Task created: 550e8400-e29b-41d4-a716-446655440000

Step 5: Monitoring task status...
  Status: pending
  Status: running
  Status: completed
✓ Task completed successfully!

Step 6: Task Results
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "failure_type": "lint",
    "files_modified": 3,
    "fix_confidence": 0.85
  }
}

🎉 PatchBot Test Complete!
```

## Testing with Real GitHub Actions

### Step 1: Set Up Webhooks

1. Go to your Sentinel repository on GitHub
2. Navigate to Settings → Webhooks → Add webhook
3. Configure:
   - **Payload URL**: `https://your-domain.com/webhooks/github/workflow_run`
   - **Content type**: `application/json`
   - **Secret**: Generate a secret and set as `GITHUB_WEBHOOK_SECRET`
   - **Events**: Select "Workflow runs"
   - **Active**: ✓

### Step 2: Configure Environment Variables

```bash
# For PatchBot agent
export ANTHROPIC_API_KEY=sk-ant-...
export GITHUB_TOKEN=ghp_...
export CONTROLLER_URL=http://localhost:8003

# For Failure Ingestion service
export GITHUB_WEBHOOK_SECRET=your-webhook-secret
export GITLAB_WEBHOOK_SECRET=your-gitlab-secret  # If using GitLab
```

### Step 3: Start PatchBot Agent

```bash
cd agents/patchbot

# Install dependencies
pip install -e .

# Run agent
python -m patchbot.agent
```

Or with Docker:

```bash
cd agents/patchbot
docker build -t sentinel-patchbot .
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
           -e GITHUB_TOKEN=$GITHUB_TOKEN \
           -e CONTROLLER_URL=http://agent-controller:8003 \
           --network sentinel_default \
           sentinel-patchbot
```

### Step 4: Trigger a Test Failure

#### Option A: Manual Workflow Dispatch

1. Go to Actions tab in GitHub
2. Select "PatchBot Integration Test"
3. Click "Run workflow"
4. Choose failure type (linting, formatting, or type_check)
5. Click "Run workflow"

#### Option B: Create Test Branch

```bash
# Create a test branch with linting errors
git checkout -b test/patchbot-lint

# Push to trigger workflow
git push origin test/patchbot-lint
```

The GitHub Actions workflow will fail, triggering the webhook to Failure Ingestion.

### Step 5: Monitor PatchBot

```bash
# Watch Agent Controller logs
docker logs -f sentinel-agent-controller

# Watch PatchBot logs (if running locally)
tail -f patchbot.log

# Check tasks via API
curl http://localhost:8003/api/v1/tasks | jq '.tasks[] | select(.status == "running")'
```

### Step 6: Verify Fix

PatchBot will:
1. Receive the failure task
2. Clone the repository
3. Analyze the failure
4. Generate a fix using AI
5. Create a new branch (e.g., `fix/ci-failure-abc123`)
6. Commit the changes
7. Create a Pull Request

Check the PR created by PatchBot:
- Go to your repository's Pull Requests
- Look for PR titled: "Fix CI failure: [error message]"
- Review the changes made by PatchBot
- Merge if satisfied

## Test Scenarios

### Scenario 1: Linting Errors

```bash
# This workflow will fail due to linting errors in example files
gh workflow run patchbot-test.yml -f failure_type=linting
```

**Expected Fix**: PatchBot adds type annotations, removes unused imports, fixes undefined variables

### Scenario 2: Formatting Issues

```bash
# This workflow will fail due to formatting issues
gh workflow run patchbot-test.yml -f failure_type=formatting
```

**Expected Fix**: PatchBot runs Black formatter and commits the formatted code

### Scenario 3: Type Check Errors

```bash
# This workflow will fail due to type checking errors
gh workflow run patchbot-test.yml -f failure_type=type_check
```

**Expected Fix**: PatchBot adds missing type annotations and fixes type mismatches

## Troubleshooting

### Webhook Not Received

**Problem**: Failure Ingestion doesn't receive webhook events

**Solutions**:
1. Check webhook is configured correctly in GitHub
2. Verify webhook secret matches `GITHUB_WEBHOOK_SECRET`
3. Check Failure Ingestion logs: `docker logs sentinel-failure-ingestion`
4. Test webhook delivery in GitHub Settings → Webhooks → Recent Deliveries

### Task Stuck in Pending

**Problem**: Task created but never starts

**Solutions**:
1. Verify PatchBot agent is running
2. Check agent registered: `curl http://localhost:8003/api/v1/agents`
3. Check agent capabilities match task type
4. Review Agent Controller logs for errors

### No PR Created

**Problem**: Fix generated but no PR created

**Solutions**:
1. Verify `GITHUB_TOKEN` has required permissions:
   - `repo` (full control)
   - `workflow` (if modifying workflows)
2. Check `OPEN_PR=true` in PatchBot config
3. Verify repository allows PR creation
4. Review PatchBot logs for GitHub API errors

### Low Fix Confidence

**Problem**: PatchBot generates fixes but confidence is low (<70%)

**Solutions**:
1. Provide more context in failure logs
2. Ensure error messages are clear and specific
3. Add known failure patterns to PatchBot
4. Review and improve prompts in `patchbot/fixer.py`

### API Rate Limits

**Problem**: Anthropic API rate limit exceeded

**Solutions**:
1. Implement request throttling in PatchBot
2. Add retry logic with exponential backoff
3. Cache frequent fixes
4. Consider using local models as fallback

## Metrics & Monitoring

### Agent Controller Metrics

```bash
# View all tasks
curl http://localhost:8003/api/v1/tasks | jq '.tasks | length'

# View completed tasks
curl http://localhost:8003/api/v1/tasks | jq '.tasks[] | select(.status == "completed")'

# View agent stats
curl http://localhost:8003/api/v1/agents | jq '.agents[] | {name: .name, total_tasks: .total_tasks, success_rate: (.successful_tasks / .total_tasks)}'
```

### Failure Ingestion Metrics

```bash
# Check GitHub webhook health
curl http://localhost:8004/webhooks/github/health

# Check GitLab webhook health
curl http://localhost:8004/webhooks/gitlab/health
```

## Advanced Testing

### Testing with Local Repository

```bash
# Clone Sentinel locally
git clone https://github.com/your-org/sentinel.git /tmp/sentinel-test

# Modify PatchBot to use local repo
export TEST_REPO_PATH=/tmp/sentinel-test

# Run PatchBot with local repository (bypasses git clone)
python -m patchbot.agent --local-repo $TEST_REPO_PATH
```

### Testing without AI (Dry Run)

```bash
# Run PatchBot in dry-run mode
export DRY_RUN=true
python -m patchbot.agent

# This will analyze failures but not generate fixes
```

### Custom Failure Patterns

Add custom patterns to `patchbot/analyzer.py`:

```python
CUSTOM_PATTERNS = [
    FailurePattern(
        pattern=r"Custom error: (.*)",
        failure_type=FailureType.CUSTOM,
        fix_strategy="custom_fix_strategy"
    ),
]
```

## Best Practices

1. **Start Small**: Test with simple linting errors before complex bugs
2. **Review Fixes**: Always review PRs created by PatchBot before merging
3. **Monitor Costs**: Track Anthropic API usage and set budgets
4. **Rate Limiting**: Configure appropriate rate limits for your team size
5. **Security**: Use separate GitHub tokens with minimal required permissions
6. **Feedback Loop**: Report fix outcomes back to InfraMind for learning

## Next Steps

After successful testing:

1. **Production Deployment**: Deploy to production environment
2. **Multi-Repository**: Enable for multiple repositories
3. **Custom Agents**: Build new agents (LogAnalyzer, ConfigOptimizer)
4. **Monitoring**: Set up Grafana dashboards for agent metrics
5. **Alerting**: Configure alerts for agent failures or low success rates

## Support

- **Documentation**: [Phase 5 Documentation](./PHASE_5_AGENT_ORCHESTRATION.md)
- **API Reference**: [API Documentation](./API_REFERENCE.md)
- **Issues**: [GitHub Issues](https://github.com/your-org/sentinel/issues)
