"""Agent SDK Client - Core client for communicating with Agent Controller."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .models import (
    AgentCapabilities,
    AgentConfig,
    AgentHeartbeat,
    AgentInfo,
    AgentTask,
    TaskResult,
    TaskUpdate,
)

logger = logging.getLogger(__name__)


class AgentClient:
    """
    Client for Sentinel AI agents to communicate with Agent Controller.

    Handles:
    - Agent registration
    - Task polling and execution
    - Progress reporting
    - Heartbeat management
    """

    def __init__(
        self,
        agent_name: str,
        version: str,
        capabilities: AgentCapabilities,
        controller_url: str = "http://localhost:8003",
        config: Optional[AgentConfig] = None,
    ):
        """
        Initialize Agent Client.

        Args:
            agent_name: Unique agent name
            version: Agent version (semver)
            capabilities: Agent capabilities
            controller_url: Agent Controller base URL
            config: Optional agent configuration
        """
        self.agent_name = agent_name
        self.version = version
        self.capabilities = capabilities
        self.controller_url = controller_url.rstrip("/")
        self.config = config or AgentConfig()

        self.agent_id: Optional[UUID] = None
        self.client = httpx.AsyncClient(
            base_url=f"{self.controller_url}/api/v1",
            timeout=30.0,
        )

        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._task_handlers: Dict[str, Callable] = {}

    async def __aenter__(self):
        """Context manager entry."""
        await self.register()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.shutdown()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def register(self) -> AgentInfo:
        """
        Register agent with Agent Controller.

        Returns:
            AgentInfo with agent ID and details

        Raises:
            httpx.HTTPError: If registration fails
        """
        logger.info(f"Registering agent: {self.agent_name} v{self.version}")

        payload = {
            "name": self.agent_name,
            "version": self.version,
            "description": self.config.description,
            "capabilities": self.capabilities.model_dump(),
            "configuration": self.config.metadata,
        }

        response = await self.client.post("/agents/", json=payload)
        response.raise_for_status()

        data = response.json()
        self.agent_id = UUID(data["id"])

        logger.info(f"✓ Agent registered: {self.agent_name} ({self.agent_id})")

        # Start heartbeat
        await self._start_heartbeat()

        return AgentInfo(**data)

    async def unregister(self) -> None:
        """Unregister agent from Agent Controller."""
        if not self.agent_id:
            return

        logger.info(f"Unregistering agent: {self.agent_id}")

        try:
            response = await self.client.delete(f"/agents/{self.agent_id}")
            response.raise_for_status()
            logger.info(f"✓ Agent unregistered: {self.agent_id}")
        except httpx.HTTPError as e:
            logger.warning(f"Failed to unregister agent: {e}")
        finally:
            self.agent_id = None

    async def get_next_task(self) -> Optional[AgentTask]:
        """
        Get next available task from queue.

        Returns:
            AgentTask or None if no tasks available
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered")

        try:
            # Get agent's queue status
            response = await self.client.get(f"/tasks/agent/{self.agent_id}/queue")
            response.raise_for_status()

            queue_data = response.json()

            if not queue_data.get("active_task_ids"):
                # No active tasks, check for pending/queued
                return None

            # Get task details
            # Note: In production, the controller should have a dequeue endpoint
            # For now, we'll list tasks and get the first one
            response = await self.client.get(
                "/tasks/",
                params={
                    "agent_id": str(self.agent_id),
                    "status": "queued",
                    "limit": 1,
                },
            )
            response.raise_for_status()

            tasks = response.json()
            if not tasks:
                return None

            task_data = tasks[0]
            return AgentTask(
                id=UUID(task_data["id"]),
                task_type=task_data["task_type"],
                context=task_data["context"],
                timeout_seconds=task_data.get("timeout_seconds", 600),
                correlation_id=UUID(task_data["correlation_id"])
                if task_data.get("correlation_id")
                else None,
            )

        except httpx.HTTPError as e:
            logger.error(f"Failed to get next task: {e}")
            return None

    async def update_task_progress(
        self,
        task_id: UUID,
        progress: float,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress value (0.0 to 1.0)
            metrics: Optional metrics dict
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered")

        update = TaskUpdate(progress=progress, metrics=metrics or {})

        try:
            response = await self.client.patch(
                f"/tasks/{task_id}",
                json=update.model_dump(exclude_none=True),
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Failed to update task progress: {e}")

    async def complete_task(
        self,
        task_id: UUID,
        result: TaskResult,
    ) -> None:
        """
        Mark task as completed.

        Args:
            task_id: Task ID
            result: Task result with status and data
        """
        if not self.agent_id:
            raise RuntimeError("Agent not registered")

        update = TaskUpdate(
            status="completed" if result.success else "failed",
            progress=1.0,
            result=result.data,
            error_message=result.error_message,
            metrics=result.metrics,
            artifacts=result.artifacts,
        )

        try:
            response = await self.client.patch(
                f"/tasks/{task_id}",
                json=update.model_dump(exclude_none=True),
            )
            response.raise_for_status()

            status = "completed" if result.success else "failed"
            logger.info(f"✓ Task {task_id} {status}")

        except httpx.HTTPError as e:
            logger.error(f"Failed to complete task: {e}")

    async def send_heartbeat(
        self,
        health_score: float,
        active_tasks: int = 0,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send heartbeat to Agent Controller.

        Args:
            health_score: Current health (0.0 to 1.0)
            active_tasks: Number of active tasks
            metrics: Optional metrics
        """
        if not self.agent_id:
            return

        heartbeat = AgentHeartbeat(
            health_score=health_score,
            active_tasks=active_tasks,
            metrics=metrics or {},
        )

        try:
            response = await self.client.post(
                f"/agents/{self.agent_id}/heartbeat",
                json=heartbeat.model_dump(),
            )
            response.raise_for_status()
            logger.debug(f"Heartbeat sent (health: {health_score:.2f})")

        except httpx.HTTPError as e:
            logger.warning(f"Failed to send heartbeat: {e}")

    def register_task_handler(
        self,
        task_type: str,
        handler: Callable[[AgentTask], Any],
    ) -> None:
        """
        Register a task handler function.

        Args:
            task_type: Type of task to handle
            handler: Async function that handles the task
        """
        self._task_handlers[task_type] = handler
        logger.info(f"Registered handler for task type: {task_type}")

    async def run(self) -> None:
        """
        Start agent task loop.

        This will continuously poll for tasks and execute them.
        """
        if not self.agent_id:
            await self.register()

        self._running = True
        logger.info(f"🤖 Agent {self.agent_name} started")

        active_tasks = 0

        while self._running:
            try:
                # Check if we can accept more tasks
                if active_tasks >= self.capabilities.max_concurrent_tasks:
                    await asyncio.sleep(1)
                    continue

                # Get next task
                task = await self.get_next_task()

                if not task:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(self.config.poll_interval)
                    continue

                # Find handler
                handler = self._task_handlers.get(task.task_type)

                if not handler:
                    logger.warning(f"No handler for task type: {task.task_type}")
                    # Mark task as failed
                    await self.complete_task(
                        task.id,
                        TaskResult(
                            success=False,
                            error_message=f"No handler for task type: {task.task_type}",
                        ),
                    )
                    continue

                # Execute task in background
                active_tasks += 1
                asyncio.create_task(self._execute_task(task, handler))

            except Exception as e:
                logger.error(f"Error in task loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _execute_task(
        self,
        task: AgentTask,
        handler: Callable[[AgentTask], Any],
    ) -> None:
        """Execute a single task."""
        logger.info(f"⚙️  Executing task {task.id} (type: {task.task_type})")

        try:
            # Execute handler
            result = await handler(task)

            # If handler returns TaskResult, use it
            if isinstance(result, TaskResult):
                await self.complete_task(task.id, result)
            else:
                # Otherwise, wrap result
                await self.complete_task(
                    task.id,
                    TaskResult(success=True, data={"result": result}),
                )

        except Exception as e:
            logger.error(f"Task {task.id} failed: {e}", exc_info=True)
            await self.complete_task(
                task.id,
                TaskResult(success=False, error_message=str(e)),
            )

    async def _start_heartbeat(self) -> None:
        """Start heartbeat background task."""
        if self._heartbeat_task:
            return

        async def heartbeat_loop():
            while self._running:
                try:
                    await self.send_heartbeat(
                        health_score=1.0,  # TODO: Calculate actual health
                        active_tasks=0,  # TODO: Track active tasks
                    )
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")

                await asyncio.sleep(self.config.heartbeat_interval)

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())

    async def shutdown(self) -> None:
        """Gracefully shutdown agent."""
        logger.info(f"Shutting down agent: {self.agent_name}")

        self._running = False

        # Cancel heartbeat
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Unregister
        await self.unregister()

        # Close HTTP client
        await self.client.aclose()

        logger.info("✓ Agent shutdown complete")
