"""Task Manager Service - Orchestrates task creation and assignment."""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentDB, AgentStatus, AgentTaskDB, TaskStatus
from .agent_registry import AgentRegistry
from .task_queue import TaskQueue

logger = logging.getLogger(__name__)


class TaskManager:
    """
    Task Manager orchestrates task creation and assignment.

    Responsibilities:
    - Create and assign tasks to capable agents
    - Monitor task progress
    - Handle task failures and retries
    - Collect task statistics
    - Integrate with InfraMind for failure correlation
    """

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        self.db = db
        self.redis = redis_client
        self.agent_registry = AgentRegistry(db)
        self.task_queue = TaskQueue(db, redis_client)

    async def create_task(
        self,
        task_type: str,
        context: Dict,
        payload: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        correlation_id: Optional[UUID] = None,
        priority: str = TaskQueue.PRIORITY_NORMAL,
    ) -> Optional[AgentTaskDB]:
        """
        Create a new task and assign to a capable agent.

        Args:
            task_type: Type of task (e.g., "ci_failure_fix")
            context: Task context with parameters
            payload: Optional large payload
            timeout_seconds: Task timeout
            correlation_id: Link to InfraMind prediction
            priority: Task priority

        Returns:
            Created task or None if no capable agent found
        """
        try:
            # Find capable agents
            capable_agents = await self.agent_registry.find_capable_agents(task_type)

            if not capable_agents:
                logger.warning(f"⚠ No capable agents found for task type: {task_type}")
                return None

            # Select best agent (highest health score)
            best_agent = max(capable_agents, key=lambda a: a.health_score)

            # Check agent capacity
            queue_depth = await self.task_queue.get_queue_depth(best_agent.id)
            active_tasks = len(await self.task_queue.get_active_tasks(best_agent.id))

            # Get agent capabilities
            result = await self.db.execute(
                select(AgentDB).where(AgentDB.id == best_agent.id)
            )
            agent = result.scalar_one()
            max_concurrent = agent.capabilities.get("max_concurrent_tasks", 5)

            # Check if agent is at capacity
            if active_tasks >= max_concurrent:
                logger.warning(
                    f"⚠ Agent {best_agent.name} at capacity ({active_tasks}/{max_concurrent})"
                )
                # Still create task but it will be queued
                priority = TaskQueue.PRIORITY_LOW

            # Create task in database
            task = AgentTaskDB(
                agent_id=best_agent.id,
                task_type=task_type,
                context=context,
                payload=payload,
                status=TaskStatus.PENDING.value,
                timeout_seconds=timeout_seconds or 600,
                correlation_id=correlation_id,
            )

            self.db.add(task)
            await self.db.commit()
            await self.db.refresh(task)

            # Enqueue task
            await self.task_queue.enqueue_task(
                agent_id=best_agent.id,
                task_id=task.id,
                task_type=task_type,
                context=context,
                priority=priority,
            )

            logger.info(
                f"✓ Task {task.id} created and assigned to agent {best_agent.name}"
            )

            return task

        except Exception as e:
            logger.error(f"✗ Failed to create task: {e}")
            await self.db.rollback()
            return None

    async def get_task(self, task_id: UUID) -> Optional[AgentTaskDB]:
        """Get task by ID."""
        result = await self.db.execute(
            select(AgentTaskDB).where(AgentTaskDB.id == task_id)
        )
        return result.scalar_one_or_none()

    async def list_tasks(
        self,
        agent_id: Optional[UUID] = None,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[AgentTaskDB]:
        """
        List tasks with filters.

        Args:
            agent_id: Filter by agent
            status: Filter by status
            task_type: Filter by type
            limit: Maximum results
            offset: Result offset

        Returns:
            List of tasks
        """
        query = select(AgentTaskDB)

        if agent_id:
            query = query.where(AgentTaskDB.agent_id == agent_id)

        if status:
            query = query.where(AgentTaskDB.status == status)

        if task_type:
            query = query.where(AgentTaskDB.task_type == task_type)

        query = query.order_by(AgentTaskDB.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_task_progress(
        self, task_id: UUID, progress: float, metrics: Optional[Dict] = None
    ) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress (0.0 to 1.0)
            metrics: Optional metrics

        Returns:
            True if updated successfully
        """
        try:
            result = await self.db.execute(
                select(AgentTaskDB).where(AgentTaskDB.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return False

            task.progress = progress
            if metrics:
                task.metrics = metrics

            await self.db.commit()
            return True

        except Exception as e:
            logger.error(f"✗ Failed to update task progress: {e}")
            return False

    async def complete_task(
        self,
        task_id: UUID,
        success: bool,
        result: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Complete a task.

        Args:
            task_id: Task ID
            success: Whether task succeeded
            result: Task result data
            error_message: Error message if failed

        Returns:
            True if completed successfully
        """
        try:
            # Update task queue
            await self.task_queue.complete_task(task_id, success, result)

            # Get task from DB
            db_result = await self.db.execute(
                select(AgentTaskDB).where(AgentTaskDB.id == task_id)
            )
            task = db_result.scalar_one_or_none()

            if not task:
                return False

            # Update agent statistics
            agent_result = await self.db.execute(
                select(AgentDB).where(AgentDB.id == task.agent_id)
            )
            agent = agent_result.scalar_one_or_none()

            if agent:
                agent.total_tasks += 1
                if success:
                    agent.successful_tasks += 1
                else:
                    agent.failed_tasks += 1

            # Update task
            task.error_message = error_message
            task.progress = 1.0 if success else task.progress

            await self.db.commit()

            # Handle retry if failed
            if not success and task.retry_count < task.max_retries:
                logger.info(f"⚠ Task {task_id} failed, scheduling retry")
                await self.task_queue.retry_task(task_id)

            logger.info(
                f"✓ Task {task_id} completed (success: {success})"
            )
            return True

        except Exception as e:
            logger.error(f"✗ Failed to complete task: {e}")
            return False

    async def cancel_task(self, task_id: UUID) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            True if cancelled successfully
        """
        return await self.task_queue.cancel_task(task_id)

    async def get_agent_queue_status(self, agent_id: UUID) -> Dict:
        """
        Get queue status for an agent.

        Args:
            agent_id: Agent ID

        Returns:
            Queue status with depth and active tasks
        """
        queue_depth = await self.task_queue.get_queue_depth(agent_id)
        active_tasks = await self.task_queue.get_active_tasks(agent_id)

        return {
            "queue_depth": queue_depth,
            "active_tasks": len(active_tasks),
            "active_task_ids": active_tasks,
        }

    async def check_task_timeouts(self) -> List[UUID]:
        """
        Check for timed-out tasks.

        Returns:
            List of timed-out task IDs
        """
        return await self.task_queue.check_timeouts()

    async def get_task_statistics(
        self, agent_id: Optional[UUID] = None
    ) -> Dict:
        """
        Get task execution statistics.

        Args:
            agent_id: Optional agent ID filter

        Returns:
            Task statistics
        """
        query = select(
            AgentTaskDB.status,
            func.count(AgentTaskDB.id).label("count"),
            func.avg(AgentTaskDB.duration_ms).label("avg_duration"),
        ).group_by(AgentTaskDB.status)

        if agent_id:
            query = query.where(AgentTaskDB.agent_id == agent_id)

        result = await self.db.execute(query)

        stats = {
            "total": 0,
            "pending": 0,
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
            "rate_limited": 0,
            "avg_duration_ms": None,
        }

        for status, count, avg_duration in result:
            stats["total"] += count
            stats[status] = count
            if avg_duration and status == TaskStatus.COMPLETED.value:
                stats["avg_duration_ms"] = float(avg_duration)

        # Calculate success rate
        total_finished = stats["completed"] + stats["failed"]
        if total_finished > 0:
            stats["success_rate"] = stats["completed"] / total_finished
        else:
            stats["success_rate"] = 0.0

        return stats

    async def get_tasks_by_correlation(
        self, correlation_id: UUID
    ) -> List[AgentTaskDB]:
        """
        Get all tasks linked to an InfraMind prediction.

        Args:
            correlation_id: InfraMind correlation ID

        Returns:
            List of related tasks
        """
        result = await self.db.execute(
            select(AgentTaskDB)
            .where(AgentTaskDB.correlation_id == correlation_id)
            .order_by(AgentTaskDB.created_at.desc())
        )

        return list(result.scalars().all())

    async def reassign_task(
        self, task_id: UUID, new_agent_id: Optional[UUID] = None
    ) -> bool:
        """
        Reassign a task to a different agent.

        Args:
            task_id: Task ID
            new_agent_id: New agent ID (if None, finds best agent)

        Returns:
            True if reassigned successfully
        """
        try:
            result = await self.db.execute(
                select(AgentTaskDB).where(AgentTaskDB.id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                return False

            # Cancel current assignment
            await self.task_queue.cancel_task(task_id)

            # Find new agent if not specified
            if not new_agent_id:
                capable_agents = await self.agent_registry.find_capable_agents(
                    task.task_type
                )
                if not capable_agents:
                    logger.warning(f"⚠ No capable agents for task {task_id}")
                    return False

                new_agent = max(capable_agents, key=lambda a: a.health_score)
                new_agent_id = new_agent.id

            # Update task
            task.agent_id = new_agent_id
            task.status = TaskStatus.PENDING.value
            task.retry_count += 1

            await self.db.commit()

            # Re-enqueue
            await self.task_queue.enqueue_task(
                agent_id=new_agent_id,
                task_id=task_id,
                task_type=task.task_type,
                context=task.context,
            )

            logger.info(f"✓ Task {task_id} reassigned to agent {new_agent_id}")
            return True

        except Exception as e:
            logger.error(f"✗ Failed to reassign task: {e}")
            return False
