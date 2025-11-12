"""Task Queue Service - Manages task queuing and distribution with Redis."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentDB, AgentTaskDB, TaskStatus

logger = logging.getLogger(__name__)


class TaskQueue:
    """
    Task Queue manages task distribution to agents.

    Uses Redis for:
    - Task queue with priority
    - Task assignment tracking
    - Task locking for workers
    - Timeout monitoring
    """

    # Redis key prefixes
    QUEUE_PREFIX = "agent:queue:"
    TASK_PREFIX = "agent:task:"
    LOCK_PREFIX = "agent:lock:"
    ASSIGNMENT_PREFIX = "agent:assignment:"

    # Queue priorities
    PRIORITY_HIGH = "high"
    PRIORITY_NORMAL = "normal"
    PRIORITY_LOW = "low"

    # TTL settings
    TASK_LOCK_TTL = 300  # 5 minutes
    TASK_DATA_TTL = 86400  # 24 hours

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client

    async def enqueue_task(
        self,
        agent_id: UUID,
        task_id: UUID,
        task_type: str,
        context: Dict[str, Any],
        priority: str = PRIORITY_NORMAL,
    ) -> bool:
        """
        Enqueue a task for an agent.

        Args:
            agent_id: Target agent ID
            task_id: Task ID
            task_type: Type of task
            context: Task context
            priority: Task priority (high, normal, low)

        Returns:
            True if enqueued successfully
        """
        try:
            # Store task data in Redis
            task_key = f"{self.TASK_PREFIX}{task_id}"
            task_data = {
                "task_id": str(task_id),
                "agent_id": str(agent_id),
                "task_type": task_type,
                "context": json.dumps(context),
                "enqueued_at": datetime.utcnow().isoformat(),
            }

            await self.redis.hset(task_key, mapping=task_data)
            await self.redis.expire(task_key, self.TASK_DATA_TTL)

            # Add to priority queue
            queue_key = f"{self.QUEUE_PREFIX}{agent_id}:{priority}"
            score = datetime.utcnow().timestamp()
            await self.redis.zadd(queue_key, {str(task_id): score})

            # Update task status in database
            result = await self.db.execute(
                select(AgentTaskDB).where(AgentTaskDB.id == task_id)
            )
            task = result.scalar_one_or_none()

            if task:
                task.status = TaskStatus.QUEUED.value
                await self.db.commit()

            logger.info(
                f"✓ Task {task_id} enqueued for agent {agent_id} (priority: {priority})"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Failed to enqueue task {task_id}: {e}")
            return False

    async def dequeue_task(self, agent_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Dequeue next available task for an agent.

        Checks queues in priority order: high -> normal -> low

        Args:
            agent_id: Agent ID

        Returns:
            Task data or None if no tasks available
        """
        priorities = [self.PRIORITY_HIGH, self.PRIORITY_NORMAL, self.PRIORITY_LOW]

        for priority in priorities:
            queue_key = f"{self.QUEUE_PREFIX}{agent_id}:{priority}"

            # Get oldest task from queue
            tasks = await self.redis.zrange(queue_key, 0, 0)

            if tasks:
                task_id = tasks[0].decode("utf-8")

                # Try to acquire lock
                if await self._acquire_task_lock(task_id):
                    # Remove from queue
                    await self.redis.zrem(queue_key, task_id)

                    # Get task data
                    task_key = f"{self.TASK_PREFIX}{task_id}"
                    task_data = await self.redis.hgetall(task_key)

                    if task_data:
                        # Update task status
                        await self._update_task_status(
                            UUID(task_id), TaskStatus.RUNNING
                        )

                        # Track assignment
                        await self._track_assignment(agent_id, UUID(task_id))

                        return {
                            "task_id": task_id,
                            "agent_id": task_data[b"agent_id"].decode("utf-8"),
                            "task_type": task_data[b"task_type"].decode("utf-8"),
                            "context": json.loads(
                                task_data[b"context"].decode("utf-8")
                            ),
                        }

        return None

    async def complete_task(
        self, task_id: UUID, success: bool, result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: Task ID
            success: Whether task succeeded
            result: Task result data

        Returns:
            True if marked successfully
        """
        try:
            # Release lock
            await self._release_task_lock(task_id)

            # Update database
            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            await self._update_task_status(task_id, status, result)

            # Remove from active assignments
            await self._remove_assignment(task_id)

            # Clean up Redis data
            task_key = f"{self.TASK_PREFIX}{task_id}"
            await self.redis.delete(task_key)

            logger.info(
                f"✓ Task {task_id} completed (success: {success})"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Failed to complete task {task_id}: {e}")
            return False

    async def retry_task(self, task_id: UUID, priority: str = PRIORITY_NORMAL) -> bool:
        """
        Retry a failed task.

        Args:
            task_id: Task ID
            priority: Priority for retry

        Returns:
            True if requeued successfully
        """
        try:
            # Get task from database
            result = await self.db.execute(
                select(AgentTaskDB).where(AgentTaskDB.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found for retry")
                return False

            # Check retry limit
            if task.retry_count >= task.max_retries:
                logger.warning(
                    f"Task {task_id} exceeded max retries ({task.max_retries})"
                )
                return False

            # Increment retry count
            task.retry_count += 1
            task.status = TaskStatus.PENDING.value
            await self.db.commit()

            # Re-enqueue
            await self.enqueue_task(
                task.agent_id,
                task_id,
                task.task_type,
                task.context,
                priority,
            )

            logger.info(
                f"✓ Task {task_id} requeued for retry ({task.retry_count}/{task.max_retries})"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Failed to retry task {task_id}: {e}")
            return False

    async def cancel_task(self, task_id: UUID) -> bool:
        """
        Cancel a queued or running task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        try:
            # Get task data
            task_key = f"{self.TASK_PREFIX}{task_id}"
            task_data = await self.redis.hgetall(task_key)

            if not task_data:
                logger.warning(f"Task {task_id} not found in Redis")
                return False

            agent_id = task_data[b"agent_id"].decode("utf-8")

            # Remove from all priority queues
            for priority in [
                self.PRIORITY_HIGH,
                self.PRIORITY_NORMAL,
                self.PRIORITY_LOW,
            ]:
                queue_key = f"{self.QUEUE_PREFIX}{agent_id}:{priority}"
                await self.redis.zrem(queue_key, str(task_id))

            # Release lock and remove assignment
            await self._release_task_lock(task_id)
            await self._remove_assignment(task_id)

            # Update database
            await self._update_task_status(task_id, TaskStatus.CANCELLED)

            # Clean up Redis
            await self.redis.delete(task_key)

            logger.info(f"✓ Task {task_id} cancelled")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to cancel task {task_id}: {e}")
            return False

    async def get_queue_depth(self, agent_id: UUID) -> Dict[str, int]:
        """
        Get queue depth for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Dict with counts per priority
        """
        depths = {}

        for priority in [self.PRIORITY_HIGH, self.PRIORITY_NORMAL, self.PRIORITY_LOW]:
            queue_key = f"{self.QUEUE_PREFIX}{agent_id}:{priority}"
            count = await self.redis.zcard(queue_key)
            depths[priority] = count

        depths["total"] = sum(depths.values())
        return depths

    async def get_active_tasks(self, agent_id: UUID) -> List[str]:
        """
        Get list of active task IDs for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of task IDs
        """
        assignment_key = f"{self.ASSIGNMENT_PREFIX}{agent_id}"
        task_ids = await self.redis.smembers(assignment_key)
        return [tid.decode("utf-8") for tid in task_ids]

    async def check_timeouts(self) -> List[UUID]:
        """
        Check for timed-out tasks and mark them as failed.

        Returns:
            List of timed-out task IDs
        """
        timed_out = []

        try:
            # Find running tasks that exceeded timeout
            cutoff_time = datetime.utcnow() - timedelta(seconds=600)  # 10 min default

            result = await self.db.execute(
                select(AgentTaskDB).where(
                    AgentTaskDB.status == TaskStatus.RUNNING.value,
                    AgentTaskDB.started_at < cutoff_time,
                )
            )

            tasks = result.scalars().all()

            for task in tasks:
                # Check if task should timeout
                timeout = task.timeout_seconds or 600
                if task.started_at < (datetime.utcnow() - timedelta(seconds=timeout)):
                    task.status = TaskStatus.FAILED.value
                    task.error_message = "Task timed out"
                    task.completed_at = datetime.utcnow()
                    task.duration_ms = int(
                        (task.completed_at - task.started_at).total_seconds() * 1000
                    )

                    # Release lock and clean up
                    await self._release_task_lock(task.id)
                    await self._remove_assignment(task.id)

                    timed_out.append(task.id)

            if timed_out:
                await self.db.commit()
                logger.warning(f"⚠ Marked {len(timed_out)} tasks as timed out")

        except Exception as e:
            logger.error(f"✗ Failed to check timeouts: {e}")

        return timed_out

    # Private helper methods

    async def _acquire_task_lock(self, task_id: str) -> bool:
        """Try to acquire exclusive lock on a task."""
        lock_key = f"{self.LOCK_PREFIX}{task_id}"
        acquired = await self.redis.set(
            lock_key, "locked", nx=True, ex=self.TASK_LOCK_TTL
        )
        return bool(acquired)

    async def _release_task_lock(self, task_id: UUID) -> None:
        """Release task lock."""
        lock_key = f"{self.LOCK_PREFIX}{task_id}"
        await self.redis.delete(lock_key)

    async def _track_assignment(self, agent_id: UUID, task_id: UUID) -> None:
        """Track task assignment to agent."""
        assignment_key = f"{self.ASSIGNMENT_PREFIX}{agent_id}"
        await self.redis.sadd(assignment_key, str(task_id))

    async def _remove_assignment(self, task_id: UUID) -> None:
        """Remove task from all agent assignments."""
        # Find which agent has this task
        result = await self.db.execute(
            select(AgentTaskDB.agent_id).where(AgentTaskDB.id == task_id)
        )
        agent_id = result.scalar_one_or_none()

        if agent_id:
            assignment_key = f"{self.ASSIGNMENT_PREFIX}{agent_id}"
            await self.redis.srem(assignment_key, str(task_id))

    async def _update_task_status(
        self,
        task_id: UUID,
        status: TaskStatus,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update task status in database."""
        db_result = await self.db.execute(
            select(AgentTaskDB).where(AgentTaskDB.id == task_id)
        )
        task = db_result.scalar_one_or_none()

        if task:
            task.status = status.value

            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.utcnow()

            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.utcnow()
                if task.started_at:
                    task.duration_ms = int(
                        (task.completed_at - task.started_at).total_seconds() * 1000
                    )

            if result:
                task.result = result

            await self.db.commit()
