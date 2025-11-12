"""Agent Registry Service - Manages agent lifecycle."""

import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentCreate, AgentDB, AgentResponse, AgentStatus, AgentUpdate

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Agent Registry manages agent lifecycle.

    Responsibilities:
    - Register/unregister agents
    - Update agent status
    - Track agent health
    - Agent discovery
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register_agent(self, agent_data: AgentCreate) -> AgentResponse:
        """
        Register a new agent.

        Args:
            agent_data: Agent creation data

        Returns:
            Registered agent

        Raises:
            ValueError: If agent with same name already exists
        """
        # Check if agent already exists
        result = await self.db.execute(select(AgentDB).where(AgentDB.name == agent_data.name))
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"Agent '{agent_data.name}' already registered")

        # Create agent
        agent = AgentDB(
            name=agent_data.name,
            version=agent_data.version,
            description=agent_data.description,
            capabilities=agent_data.capabilities.model_dump(),
            configuration=agent_data.configuration,
            status=AgentStatus.ACTIVE.value,
            health_score=1.0,
            last_heartbeat=datetime.utcnow(),
        )

        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)

        logger.info(f"✓ Agent registered: {agent.name} v{agent.version} ({agent.id})")

        return AgentResponse.model_validate(agent)

    async def get_agent(self, agent_id: UUID) -> Optional[AgentResponse]:
        """Get agent by ID."""
        result = await self.db.execute(select(AgentDB).where(AgentDB.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return AgentResponse.model_validate(agent)

    async def get_agent_by_name(self, name: str) -> Optional[AgentResponse]:
        """Get agent by name."""
        result = await self.db.execute(select(AgentDB).where(AgentDB.name == name))
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return AgentResponse.model_validate(agent)

    async def list_agents(
        self, status: Optional[str] = None, limit: int = 100, offset: int = 0
    ) -> List[AgentResponse]:
        """
        List all agents.

        Args:
            status: Filter by status (active, paused, failed, offline)
            limit: Maximum number of agents to return
            offset: Number of agents to skip

        Returns:
            List of agents
        """
        query = select(AgentDB)

        if status:
            query = query.where(AgentDB.status == status)

        query = query.order_by(AgentDB.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        agents = result.scalars().all()

        return [AgentResponse.model_validate(agent) for agent in agents]

    async def update_agent(
        self, agent_id: UUID, update_data: AgentUpdate
    ) -> Optional[AgentResponse]:
        """
        Update agent.

        Args:
            agent_id: Agent ID
            update_data: Update data

        Returns:
            Updated agent or None if not found
        """
        result = await self.db.execute(select(AgentDB).where(AgentDB.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Update fields
        if update_data.version is not None:
            agent.version = update_data.version

        if update_data.description is not None:
            agent.description = update_data.description

        if update_data.capabilities is not None:
            agent.capabilities = update_data.capabilities.model_dump()

        if update_data.configuration is not None:
            agent.configuration = update_data.configuration

        if update_data.status is not None:
            agent.status = update_data.status

        agent.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(agent)

        logger.info(f"✓ Agent updated: {agent.name} ({agent.id})")

        return AgentResponse.model_validate(agent)

    async def delete_agent(self, agent_id: UUID) -> bool:
        """
        Delete (unregister) agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if deleted, False if not found
        """
        result = await self.db.execute(select(AgentDB).where(AgentDB.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return False

        await self.db.delete(agent)
        await self.db.commit()

        logger.info(f"✓ Agent deleted: {agent.name} ({agent_id})")

        return True

    async def update_heartbeat(
        self, agent_id: UUID, health_score: float, metrics: dict
    ) -> bool:
        """
        Update agent heartbeat.

        Args:
            agent_id: Agent ID
            health_score: Current health score (0.0-1.0)
            metrics: Agent metrics

        Returns:
            True if updated, False if agent not found
        """
        result = await self.db.execute(select(AgentDB).where(AgentDB.id == agent_id))
        agent = result.scalar_one_or_none()

        if not agent:
            return False

        agent.health_score = health_score
        agent.last_heartbeat = datetime.utcnow()

        # Update status based on health
        if health_score < 0.3:
            agent.status = AgentStatus.FAILED.value
        elif agent.status == AgentStatus.FAILED.value and health_score > 0.7:
            agent.status = AgentStatus.ACTIVE.value

        await self.db.commit()

        return True

    async def get_agent_statistics(self) -> dict:
        """Get agent statistics."""
        # Count by status
        result = await self.db.execute(
            select(AgentDB.status, func.count(AgentDB.id)).group_by(AgentDB.status)
        )

        stats = {"total": 0, "active": 0, "paused": 0, "failed": 0, "offline": 0}

        for status, count in result:
            stats["total"] += count
            stats[status] = count

        return stats

    async def find_capable_agents(self, task_type: str) -> List[AgentResponse]:
        """
        Find agents capable of handling a task type.

        Args:
            task_type: Type of task

        Returns:
            List of capable agents
        """
        result = await self.db.execute(
            select(AgentDB).where(
                AgentDB.status == AgentStatus.ACTIVE.value,
                AgentDB.capabilities.op("->>")("supported_tasks").contains([task_type]),
            )
        )

        agents = result.scalars().all()

        return [AgentResponse.model_validate(agent) for agent in agents]
