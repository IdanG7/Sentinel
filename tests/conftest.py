"""Pytest configuration for integration tests."""

import sys
from pathlib import Path

import pytest
import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Add services to path
sys.path.insert(0, str(Path(__file__).parent.parent / "services" / "control-api"))

from app.core.database import Base


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create test database."""
    # Use in-memory SQLite for tests
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def mock_kafka_producer():
    """Mock Kafka producer for testing."""
    from unittest.mock import AsyncMock

    producer = AsyncMock()
    producer.start = AsyncMock()
    producer.stop = AsyncMock()
    producer.send = AsyncMock()
    return producer


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine for testing."""
    from unittest.mock import Mock
    from uuid import uuid4
    from datetime import datetime
    from sentinel_policy import PolicyEvaluationResult

    engine = Mock()
    engine.evaluate.return_value = PolicyEvaluationResult(
        action_plan_id=uuid4(),
        approved=True,
        violations=[],
        evaluated_at=datetime.utcnow(),
        mode="enforce",
        duration_ms=10.0,
    )
    return engine
