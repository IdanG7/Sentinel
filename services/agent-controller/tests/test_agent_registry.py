"""Tests for agent registry service."""

import pytest
from datetime import datetime
from uuid import uuid4

from app.models.database import AgentDB, AgentStatus
from app.services.agent_registry import AgentRegistry


@pytest.fixture
def agent_registry():
    """Create agent registry instance."""
    return AgentRegistry()


def test_validate_agent_registration():
    """Test agent registration validation."""
    # Valid registration
    valid_data = {
        "name": "test-agent",
        "version": "1.0.0",
        "capabilities": {
            "supported_tasks": ["test_task"],
            "max_concurrent_tasks": 5,
        },
    }

    registry = AgentRegistry()
    # Should not raise
    assert registry._validate_agent_data(valid_data) is None


def test_agent_capabilities_validation():
    """Test agent capabilities validation."""
    registry = AgentRegistry()

    # Valid capabilities
    valid_caps = {
        "supported_tasks": ["task1", "task2"],
        "max_concurrent_tasks": 3,
    }
    assert registry._validate_capabilities(valid_caps) is None

    # Invalid - missing required fields
    invalid_caps = {"max_concurrent_tasks": 3}
    with pytest.raises(ValueError):
        registry._validate_capabilities(invalid_caps)


def test_agent_status_values():
    """Test agent status enum values."""
    assert AgentStatus.ACTIVE.value == "active"
    assert AgentStatus.PAUSED.value == "paused"
    assert AgentStatus.FAILED.value == "failed"
    assert AgentStatus.OFFLINE.value == "offline"


def test_agent_db_model():
    """Test AgentDB model creation."""
    agent = AgentDB(
        id=uuid4(),
        name="test-agent",
        version="1.0.0",
        description="Test agent",
        capabilities={"supported_tasks": ["test"]},
        status=AgentStatus.ACTIVE.value,
        health_score=1.0,
        created_at=datetime.utcnow(),
    )

    assert agent.name == "test-agent"
    assert agent.version == "1.0.0"
    assert agent.status == AgentStatus.ACTIVE.value
    assert agent.health_score == 1.0
