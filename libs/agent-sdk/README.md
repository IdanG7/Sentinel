# Sentinel Agent SDK

Python SDK for building autonomous AI agents that work with the Sentinel Agent Controller.

## Installation

```bash
pip install -e libs/agent-sdk
```

## Quick Start

```python
from agent_sdk import AgentClient, AgentCapabilities, TaskResult

# Define agent capabilities
capabilities = AgentCapabilities(
    supported_tasks=["ci_failure_fix", "code_review"],
    max_concurrent_tasks=5,
    timeout_seconds=600,
)

# Create agent client
async with AgentClient(
    agent_name="my-agent",
    version="1.0.0",
    capabilities=capabilities,
    controller_url="http://localhost:8003",
) as agent:

    # Register task handler
    async def handle_task(task):
        # Process task
        result = await process_task(task.context)

        # Return result
        return TaskResult(
            success=True,
            data={"result": result},
        )

    agent.register_task_handler("ci_failure_fix", handle_task)

    # Start agent (blocks until shutdown)
    await agent.run()
```

## Features

- **Automatic Registration**: Agents register themselves with the Agent Controller
- **Task Polling**: Continuously polls for new tasks based on capabilities
- **Progress Reporting**: Update task progress and metrics during execution
- **Heartbeat Management**: Automatic health reporting to controller
- **Error Handling**: Built-in retry logic and error reporting
- **Type Safety**: Full Pydantic validation for all data models

## Core Concepts

### Agent Registration

Agents register with the controller providing:
- **Name**: Unique identifier
- **Version**: Semantic version
- **Capabilities**: Task types supported and concurrency limits
- **Configuration**: Optional metadata

### Task Handling

Tasks are pulled from the controller's priority queue:
1. Agent polls for next available task
2. Task is dispatched to registered handler
3. Handler processes task and returns result
4. Result is sent back to controller

### Health Monitoring

Agents send periodic heartbeats with:
- Health score (0.0 to 1.0)
- Active task count
- Custom metrics

## API Reference

### AgentClient

Main client for agent communication.

**Methods:**
- `register()` - Register agent with controller
- `unregister()` - Unregister from controller
- `get_next_task()` - Poll for next task
- `update_task_progress()` - Report progress
- `complete_task()` - Mark task complete
- `send_heartbeat()` - Send health status
- `register_task_handler()` - Register task type handler
- `run()` - Start agent task loop

### AgentCapabilities

Defines what tasks an agent can handle.

**Fields:**
- `supported_tasks: List[str]` - Task type identifiers
- `max_concurrent_tasks: int` - Maximum parallel tasks (1-50)
- `supported_failure_types: Optional[List[str]]` - Specific failure types
- `timeout_seconds: int` - Default task timeout (60-3600)

### TaskResult

Result of task execution.

**Fields:**
- `success: bool` - Whether task succeeded
- `data: Optional[Dict]` - Result data
- `error_message: Optional[str]` - Error description if failed
- `artifacts: Optional[List[Dict]]` - Generated artifacts (files, PRs, etc.)
- `metrics: Optional[Dict]` - Performance metrics

## Examples

See `agents/patchbot/` for a complete agent implementation.

## Development

```bash
# Install dev dependencies
pip install -e "libs/agent-sdk[dev]"

# Run tests
pytest libs/agent-sdk/tests

# Format code
black libs/agent-sdk
ruff check libs/agent-sdk
```
