"""Client for Agent Controller API."""

import logging
from typing import Any, Dict

import httpx

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def submit_fix_task(
    agent_name: str,
    task_type: str,
    context: Dict[str, Any],
    timeout_seconds: int = 1800,
) -> str:
    """
    Submit a fix task to the Agent Controller.

    Args:
        agent_name: Name of agent to execute task
        task_type: Type of task (e.g., "ci_failure_fix")
        context: Task context data
        timeout_seconds: Task timeout

    Returns:
        Task ID

    Raises:
        httpx.HTTPError: If request fails
    """
    url = f"{settings.agent_controller_url}/api/v1/tasks"

    payload = {
        "agent_name": agent_name,
        "task_type": task_type,
        "context": context,
        "timeout_seconds": timeout_seconds,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()

            result = response.json()
            task_id = result.get("id")

            logger.info(f"✓ Submitted task {task_id} to agent-controller")

            return task_id

    except httpx.HTTPError as e:
        logger.error(f"Failed to submit task to agent-controller: {e}")
        raise
