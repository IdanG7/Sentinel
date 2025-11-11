"""Event publishing for Kafka integration."""

import json
import logging
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from aiokafka import AIOKafkaProducer

from .config import Settings

logger = logging.getLogger(__name__)


class EventPublisher:
    """
    Publishes events to Kafka for audit logging and service communication.
    """

    def __init__(self, settings: Settings):
        """
        Initialize event publisher.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.producer: Optional[AIOKafkaProducer] = None
        self._initialized = False

    async def start(self) -> None:
        """Start the Kafka producer."""
        if self._initialized:
            return

        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            await self.producer.start()
            self._initialized = True
            logger.info("Kafka producer started successfully")
        except Exception as e:
            logger.error(f"Failed to start Kafka producer: {e}")
            # Continue without Kafka for now (graceful degradation)
            self._initialized = False

    async def stop(self) -> None:
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            self._initialized = False
            logger.info("Kafka producer stopped")

    async def publish_event(
        self,
        topic: str,
        event_type: str,
        data: dict[str, Any],
        key: Optional[str] = None,
    ) -> bool:
        """
        Publish an event to Kafka.

        Args:
            topic: Kafka topic name
            event_type: Type of event (e.g., "workload.created", "deployment.scaled")
            data: Event payload
            key: Optional partition key

        Returns:
            True if published successfully, False otherwise
        """
        if not self._initialized or not self.producer:
            logger.warning(f"Kafka not available, skipping event: {event_type}")
            return False

        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": self._serialize_data(data),
        }

        try:
            key_bytes = key.encode("utf-8") if key else None
            await self.producer.send(topic, value=event, key=key_bytes)
            logger.debug(f"Published event {event_type} to topic {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish event {event_type}: {e}")
            return False

    def _serialize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Serialize data for JSON encoding.

        Handles UUIDs, datetimes, and other non-JSON types.
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, UUID):
                result[key] = str(value)
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_data(value)
            elif isinstance(value, list):
                result[key] = [
                    self._serialize_data(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                result[key] = value
        return result

    # Convenience methods for specific event types
    async def publish_audit_event(
        self,
        actor: str,
        verb: str,
        target: dict[str, Any],
        result: str,
        reason: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Publish an audit log event.

        Args:
            actor: User or service performing the action
            verb: Action verb (create, update, delete, scale, etc.)
            target: Target resource information
            result: Result of the action (success, failure, rejected)
            reason: Optional reason for the action or failure
            metadata: Optional additional metadata

        Returns:
            True if published successfully
        """
        return await self.publish_event(
            topic="sentinel.audit",
            event_type="audit.log",
            data={
                "actor": actor,
                "verb": verb,
                "target": target,
                "result": result,
                "reason": reason,
                "metadata": metadata or {},
            },
            key=actor,
        )

    async def publish_deployment_event(
        self,
        deployment_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish a deployment lifecycle event.

        Args:
            deployment_id: Deployment UUID
            event_type: Event type (deployment.created, deployment.scaled, etc.)
            data: Event data

        Returns:
            True if published successfully
        """
        return await self.publish_event(
            topic="sentinel.deployments",
            event_type=event_type,
            data=data,
            key=str(deployment_id),
        )

    async def publish_action_plan_event(
        self,
        plan_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish an action plan event.

        Args:
            plan_id: Action plan UUID
            event_type: Event type (action_plan.created, action_plan.validated, etc.)
            data: Event data

        Returns:
            True if published successfully
        """
        return await self.publish_event(
            topic="sentinel.action-plans",
            event_type=event_type,
            data=data,
            key=str(plan_id),
        )

    async def publish_policy_event(
        self,
        policy_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """
        Publish a policy event.

        Args:
            policy_id: Policy UUID
            event_type: Event type (policy.created, policy.updated, etc.)
            data: Event data

        Returns:
            True if published successfully
        """
        return await self.publish_event(
            topic="sentinel.policies",
            event_type=event_type,
            data=data,
            key=str(policy_id),
        )


# Global event publisher instance
_event_publisher: Optional[EventPublisher] = None


def get_event_publisher() -> EventPublisher:
    """
    Get the global event publisher instance.

    Returns:
        EventPublisher instance
    """
    global _event_publisher
    if _event_publisher is None:
        from .config import get_settings

        _event_publisher = EventPublisher(get_settings())
    return _event_publisher


async def init_event_publisher(settings: Settings) -> None:
    """
    Initialize the global event publisher.

    Args:
        settings: Application settings
    """
    global _event_publisher
    _event_publisher = EventPublisher(settings)
    await _event_publisher.start()


async def shutdown_event_publisher() -> None:
    """Shutdown the global event publisher."""
    global _event_publisher
    if _event_publisher:
        await _event_publisher.stop()
        _event_publisher = None
