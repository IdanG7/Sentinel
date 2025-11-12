# PatchBot Quick Start

Get PatchBot running in 5 minutes!

## 1. Start Services (2 minutes)

```bash
# Start all required services
docker-compose up -d postgres redis agent-controller failure-ingestion

# Wait for services to be ready
sleep 10

# Verify they're running
curl http://localhost:8003/health  # Agent Controller
curl http://localhost:8004/health  # Failure Ingestion
```

## 2. Test It Works (1 minute)

```bash
# Run the test script
./scripts/test-patchbot.sh
```

You should see:
```
✓ Task created: [task-id]
✓ Task completed successfully!
```

## 3. (Optional) Run PatchBot Agent with Real Fixes

If you want PatchBot to actually generate AI-powered fixes and create PRs:

```bash
# Set your API keys
export ANTHROPIC_API_KEY=sk-ant-...  # Get from console.anthropic.com
export GITHUB_TOKEN=ghp_...          # Get from github.com/settings/tokens

# Install PatchBot
cd agents/patchbot
pip install -e .

# Run it
python -m patchbot.agent
```

Now when the test script runs, PatchBot will:
1. Receive the failure
2. Generate an AI fix
3. Create a PR (if configured)

## 4. Test with Real CI/CD

### Set up GitHub webhook:

1. Go to your repo → Settings → Webhooks
2. Add webhook:
   - URL: `https://your-server.com/webhooks/github/workflow_run`
   - Content type: `application/json`
   - Events: Select "Workflow runs"

3. Trigger a failure:
```bash
# Create branch with intentional errors
git checkout -b test/patchbot-lint
git push origin test/patchbot-lint
```

The GitHub Actions workflow will fail → webhook fires → PatchBot fixes it!

## What's Next?

- Read the full [Testing Guide](docs/PATCHBOT_TESTING_GUIDE.md)
- Review [Phase 5 Documentation](docs/PHASE_5_AGENT_ORCHESTRATION.md)
- Check example errors in `tests/patchbot-examples/`

## Troubleshooting

**Services won't start:**
```bash
docker-compose logs agent-controller
docker-compose logs failure-ingestion
```

**Webhook not working:**
- Check GitHub webhook deliveries
- Verify `GITHUB_WEBHOOK_SECRET` matches

**No PRs created:**
- Ensure `GITHUB_TOKEN` has `repo` permission
- Check `OPEN_PR=true` in agent config

## Architecture

```
GitHub Actions Fail → Webhook → Failure Ingestion → Agent Controller → PatchBot
                                                                            ↓
GitHub PR Created ← Fix Generated ← AI (Claude) ← Repository Cloned ←──────┘
```

## Example Workflow

1. Developer pushes code with linting error
2. GitHub Actions fails
3. Webhook sent to Sentinel
4. Failure Ingestion parses error
5. Task created in Agent Controller
6. PatchBot picks up task
7. PatchBot analyzes logs
8. Claude generates fix
9. Fix applied and tested
10. PR created automatically
11. Developer reviews and merges

**Time to fix: < 2 minutes** (vs hours of developer time!)

---

**Ready to see it in action? Run `./scripts/test-patchbot.sh` now!**
