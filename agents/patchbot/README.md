# PatchBot - Autonomous CI/CD Failure Resolution

PatchBot is an AI-powered agent that automatically fixes CI/CD failures by:
1. Analyzing failure logs and error messages
2. Generating code fixes using Claude AI
3. Creating pull requests with the fixes
4. Tracking fix outcomes and success rates

## Features

- **Intelligent Analysis**: Understands test failures, build errors, linting issues, and more
- **AI-Powered Fixes**: Uses Claude Sonnet 4 to generate high-quality code fixes
- **Automated PRs**: Creates well-documented pull requests with explanations
- **Safety First**: Calculates confidence scores and requires review before merging
- **Multi-Language**: Supports Python, JavaScript/TypeScript, Go, Java, Rust, and more

## Supported Failure Types

- **Test Failures**: pytest, unittest, jest, mocha
- **Build Errors**: Compilation failures, dependency issues
- **Linting**: ruff, eslint, pylint
- **Type Errors**: mypy, TypeScript compiler
- **General**: Any failure with clear error messages

## Installation

```bash
# Install with dependencies
pip install -e agents/patchbot

# Or using the Agent SDK separately
pip install -e libs/agent-sdk
pip install -e agents/patchbot
```

## Configuration

PatchBot uses environment variables for configuration:

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."
export GITHUB_TOKEN="ghp_..."
export AGENT_CONTROLLER_URL="http://localhost:8003"

# Optional
export CLAUDE_MODEL="claude-sonnet-4-20250514"
export AUTO_MERGE_CONFIDENCE_THRESHOLD="0.9"
export WORKSPACE_DIR="/tmp/patchbot-workspace"
export GIT_AUTHOR_NAME="PatchBot"
export GIT_AUTHOR_EMAIL="patchbot@sentinel.ai"
```

Or use a `.env` file in the `agents/patchbot` directory.

## Usage

### Running PatchBot

```bash
cd agents/patchbot
python -m patchbot.agent
```

### Running with Docker

```bash
docker build -t patchbot agents/patchbot
docker run -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
           -e GITHUB_TOKEN=$GITHUB_TOKEN \
           -e AGENT_CONTROLLER_URL=http://host.docker.internal:8003 \
           patchbot
```

### Programmatic Usage

```python
from patchbot import PatchBot, get_config

# Create and run bot
config = get_config()
bot = PatchBot(config)

await bot.run()
```

## How It Works

### 1. Task Reception

PatchBot registers with the Agent Controller and polls for `ci_failure_fix` tasks:

```python
{
    "task_type": "ci_failure_fix",
    "context": {
        "repository": "org/repo",
        "repository_url": "https://github.com/org/repo.git",
        "branch": "main",
        "failure_type": "test",
        "error_log": "...",
        "build_url": "https://ci.example.com/builds/123"
    }
}
```

### 2. Failure Analysis

The analyzer extracts:
- Error messages and stack traces
- Affected files and line numbers
- Failure signatures for deduplication

### 3. Fix Generation

Claude AI analyzes the failure and generates:
- Root cause analysis
- Code fixes with explanations
- Confidence scores (0.0 to 1.0)

### 4. Git Operations

PatchBot:
- Clones the repository
- Creates a new branch (`patchbot/fix-...`)
- Applies the fixes
- Commits with detailed message
- Pushes to remote

### 5. Pull Request Creation

Creates a PR with:
- Clear title and description
- Explanation of the problem
- Details of the fix
- Confidence score
- Link to original build

### 6. Result Tracking

Reports back to Agent Controller:
- Fix success/failure
- PR URL and number
- Confidence score
- Duration and metrics

## Architecture

```
┌─────────────────────────────────────────┐
│         Agent Controller                 │
│  (Manages tasks and agent lifecycle)    │
└────────────┬────────────────────────────┘
             │
             │ Tasks
             ↓
┌─────────────────────────────────────────┐
│           PatchBot Agent                 │
│  ┌─────────────────────────────────┐   │
│  │  FailureAnalyzer                │   │
│  │  - Parse logs                   │   │
│  │  - Extract errors               │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  CodeFixer (Claude AI)          │   │
│  │  - Analyze failure              │   │
│  │  - Generate fixes               │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────────────────────────┐   │
│  │  GitManager                     │   │
│  │  - Clone repo                   │   │
│  │  - Apply fixes                  │   │
│  │  - Create PR                    │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
             │
             │ Pull Request
             ↓
┌─────────────────────────────────────────┐
│            GitHub                        │
└─────────────────────────────────────────┘
```

## Metrics

PatchBot tracks:
- **Fix Success Rate**: Percentage of fixes that resolve the issue
- **Merge Rate**: Percentage of PRs that get merged
- **Time to Fix**: Duration from failure to PR creation
- **Time to Merge**: Duration from PR to merge
- **Confidence Accuracy**: How well confidence scores predict success

## Safety and Reliability

- **Confidence Scores**: Every fix includes a confidence score (0.0-1.0)
- **Auto-Merge Threshold**: Only fixes above threshold are auto-merged (default: 0.9)
- **Human Review**: All PRs require review unless above auto-merge threshold
- **Detailed Logging**: Complete audit trail of all operations
- **Graceful Failures**: Errors don't crash the agent, just fail the task

## Development

### Running Tests

```bash
pytest agents/patchbot/tests
```

### Code Quality

```bash
# Format
black agents/patchbot

# Lint
ruff check agents/patchbot
```

### Adding Support for New Failure Types

1. Add patterns to `analyzer.py`:
```python
PATTERNS = {
    "new_type": [
        r"pattern_to_match_errors",
    ],
}
```

2. Update capabilities in `agent.py`:
```python
supported_failure_types=["test", "build", "lint", "new_type"]
```

## Metrics Dashboard

View PatchBot metrics in Grafana:
- Fix success rate over time
- Average time to fix
- Failures by type
- Confidence vs. actual success correlation

## Troubleshooting

### Agent won't start
- Check `ANTHROPIC_API_KEY` is set
- Verify `AGENT_CONTROLLER_URL` is reachable
- Check logs for detailed error messages

### Fixes not working
- Review confidence score (low confidence = uncertain fix)
- Check if error analysis was accurate
- Verify file paths are correct

### PRs not created
- Check `GITHUB_TOKEN` has repo write permissions
- Verify repository name format (`org/repo`)
- Check GitHub API rate limits

## Contributing

See the main Sentinel contributing guide.

## License

Part of the Sentinel project.
