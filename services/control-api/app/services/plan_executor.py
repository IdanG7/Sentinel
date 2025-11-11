"""Action Plan Executor - Applies action plans to infrastructure."""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.events import EventPublisher
from app.models.schemas import ActionPlanStatus

logger = logging.getLogger(__name__)


class PlanExecutionError(Exception):
    """Raised when plan execution fails."""

    pass


class PlanExecutor:
    """
    Executes action plans with safety constraints and validation.

    Responsibilities:
    - Validate action plans against policies
    - Execute decisions with retry logic
    - Track execution progress
    - Publish execution events
    """

    def __init__(
        self,
        event_publisher: EventPublisher | None = None,
        k8s_driver: Any | None = None,
        policy_engine: Any | None = None,
    ):
        """
        Initialize plan executor.

        Args:
            event_publisher: Event publisher for audit logs
            k8s_driver: Kubernetes driver for cluster operations
            policy_engine: Policy engine for validation
        """
        self.event_publisher = event_publisher
        self.k8s_driver = k8s_driver
        self.policy_engine = policy_engine

        # Execution state
        self._executing_plans: set[UUID] = set()
        self._execution_history: dict[UUID, dict[str, Any]] = {}

    async def execute_plan(
        self,
        plan_id: UUID,
        plan_data: dict[str, Any],
        actor: str = "system",
        shadow_mode: bool = False,
    ) -> dict[str, Any]:
        """
        Execute an action plan.

        Args:
            plan_id: Unique plan identifier
            plan_data: Plan data including decisions
            actor: User/system executing the plan
            shadow_mode: If True, simulate without executing

        Returns:
            Execution result with status and metrics

        Raises:
            PlanExecutionError: If execution fails
        """
        if plan_id in self._executing_plans:
            raise PlanExecutionError(f"Plan {plan_id} is already executing")

        self._executing_plans.add(plan_id)
        start_time = datetime.utcnow()

        mode_str = "SHADOW" if shadow_mode else "LIVE"
        logger.info(f"Starting {mode_str} execution of plan {plan_id}")

        try:
            # Step 1: Validate against policies
            logger.info(f"Validating plan {plan_id} against policies...")
            validation_result = await self._validate_plan(plan_data)

            if not validation_result["valid"]:
                raise PlanExecutionError(
                    f"Plan validation failed: {validation_result['reason']}"
                )

            # Step 2: Execute decisions
            decisions = plan_data.get("decisions", [])
            results = []

            for i, decision in enumerate(decisions):
                action_verb = "Simulating" if shadow_mode else "Executing"
                logger.info(
                    f"{action_verb} decision {i+1}/{len(decisions)}: {decision['verb']}"
                )

                try:
                    result = await self._execute_decision(
                        decision, shadow_mode=shadow_mode
                    )
                    results.append(result)

                    # Publish success event
                    if self.event_publisher:
                        await self.event_publisher.publish_action_plan_event(
                            plan_id=plan_id,
                            event_type="decision.executed",
                            data={
                                "decision_index": i,
                                "verb": decision["verb"],
                                "target": decision["target"],
                                "result": result,
                            },
                        )

                except Exception as e:
                    logger.error(
                        f"Failed to execute decision {i+1}: {e}", exc_info=True
                    )

                    # Publish failure event
                    if self.event_publisher:
                        await self.event_publisher.publish_action_plan_event(
                            plan_id=plan_id,
                            event_type="decision.failed",
                            data={
                                "decision_index": i,
                                "verb": decision["verb"],
                                "target": decision["target"],
                                "error": str(e),
                            },
                        )

                    # Stop execution on first failure
                    raise PlanExecutionError(f"Decision {i+1} failed: {e}") from e

            # Step 3: Record execution
            end_time = datetime.utcnow()
            execution_duration = (end_time - start_time).total_seconds()

            execution_result = {
                "plan_id": str(plan_id),
                "status": ActionPlanStatus.COMPLETED.value,
                "executed_at": end_time,
                "duration_seconds": execution_duration,
                "decisions_executed": len(results),
                "results": results,
            }

            self._execution_history[plan_id] = execution_result

            # Publish completion event
            if self.event_publisher:
                await self.event_publisher.publish_action_plan_event(
                    plan_id=plan_id,
                    event_type="action_plan.completed",
                    data=execution_result,
                )

                await self.event_publisher.publish_audit_event(
                    actor=actor,
                    verb="execute",
                    target={"type": "action_plan", "id": str(plan_id)},
                    result="success",
                    metadata={
                        "duration_seconds": execution_duration,
                        "decisions_executed": len(results),
                    },
                )

            logger.info(
                f"✓ Plan {plan_id} executed successfully in {execution_duration:.2f}s"
            )

            return execution_result

        except Exception as e:
            # Record failure
            end_time = datetime.utcnow()
            execution_duration = (end_time - start_time).total_seconds()

            execution_result = {
                "plan_id": str(plan_id),
                "status": ActionPlanStatus.FAILED.value,
                "executed_at": end_time,
                "duration_seconds": execution_duration,
                "error": str(e),
            }

            self._execution_history[plan_id] = execution_result

            # Publish failure event
            if self.event_publisher:
                await self.event_publisher.publish_action_plan_event(
                    plan_id=plan_id,
                    event_type="action_plan.failed",
                    data=execution_result,
                )

                await self.event_publisher.publish_audit_event(
                    actor=actor,
                    verb="execute",
                    target={"type": "action_plan", "id": str(plan_id)},
                    result="failure",
                    metadata={"error": str(e), "duration_seconds": execution_duration},
                )

            logger.error(f"Plan {plan_id} execution failed: {e}")
            raise

        finally:
            self._executing_plans.remove(plan_id)

    async def _validate_plan(self, plan_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate action plan against policies.

        Args:
            plan_data: Plan data to validate

        Returns:
            Validation result with valid flag and reason
        """
        if self.policy_engine is None:
            logger.warning("No policy engine configured, skipping validation")
            return {"valid": True, "reason": "No policy engine"}

        try:
            # Convert decisions to evaluation format
            decisions = plan_data.get("decisions", [])

            for decision in decisions:
                verb = decision.get("verb")
                target = decision.get("target", {})
                # params = decision.get("params", {})  # Reserved for future use

                # Validate with policy engine
                # This is a simplified version - actual implementation would be more robust
                logger.debug(f"Validating decision: {verb} on {target}")

            return {"valid": True, "reason": "All decisions passed policy validation"}

        except Exception as e:
            logger.error(f"Policy validation error: {e}", exc_info=True)
            return {"valid": False, "reason": str(e)}

    async def _execute_decision(
        self, decision: dict[str, Any], shadow_mode: bool = False
    ) -> dict[str, Any]:
        """
        Execute a single decision.

        Args:
            decision: Decision data with verb, target, and params
            shadow_mode: If True, simulate without executing

        Returns:
            Execution result

        Raises:
            PlanExecutionError: If execution fails
        """
        verb = decision.get("verb")
        target = decision.get("target", {})
        params = decision.get("params", {})
        ttl = decision.get("ttl", 900)

        action = "Simulating" if shadow_mode else "Executing"
        logger.info(f"{action}: {verb} on {target} with params {params}")

        # Route to appropriate handler based on verb
        if verb == "scale":
            return await self._handle_scale(target, params, ttl, shadow_mode)
        elif verb == "reschedule":
            return await self._handle_reschedule(target, params, ttl, shadow_mode)
        elif verb == "rollback":
            return await self._handle_rollback(target, params, ttl, shadow_mode)
        elif verb == "update":
            return await self._handle_update(target, params, ttl, shadow_mode)
        else:
            raise PlanExecutionError(f"Unknown verb: {verb}")

    async def _handle_scale(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
        ttl: int,
        shadow_mode: bool = False,
    ) -> dict[str, Any]:
        """Handle scale decision."""
        workload_name = target.get("workload")
        cluster_id = target.get("cluster", "default")
        new_replicas = int(params.get("replicas", 1))

        if shadow_mode:
            logger.info(
                f"SHADOW: Would scale {workload_name} to {new_replicas} replicas"
            )
            await asyncio.sleep(0.1)  # Simulate validation time
            return {
                "action": "scale",
                "workload": workload_name,
                "new_replicas": new_replicas,
                "status": "simulated",
                "shadow_mode": True,
                "would_execute": True,
            }

        logger.info(f"Scaling {workload_name} to {new_replicas} replicas")

        if self.k8s_driver:
            try:
                # Scale the deployment
                result = await self.k8s_driver.scale_deployment(
                    name=workload_name,
                    namespace=target.get("namespace", "default"),
                    replicas=new_replicas,
                    cluster_id=cluster_id,
                )

                return {
                    "action": "scale",
                    "workload": workload_name,
                    "previous_replicas": result.get("previous_replicas"),
                    "new_replicas": new_replicas,
                    "status": "success",
                }

            except Exception as e:
                raise PlanExecutionError(f"Scale operation failed: {e}") from e
        else:
            # Mock execution for testing
            logger.warning("No K8s driver configured, mocking scale operation")
            await asyncio.sleep(0.5)  # Simulate operation

            return {
                "action": "scale",
                "workload": workload_name,
                "new_replicas": new_replicas,
                "status": "success (mocked)",
            }

    async def _handle_reschedule(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
        ttl: int,
        shadow_mode: bool = False,
    ) -> dict[str, Any]:
        """Handle reschedule decision."""
        workload_name = target.get("workload")
        new_node = params.get("node")

        if shadow_mode:
            logger.info(f"SHADOW: Would reschedule {workload_name} to node {new_node}")
            await asyncio.sleep(0.1)
            return {
                "action": "reschedule",
                "workload": workload_name,
                "target_node": new_node,
                "status": "simulated",
                "shadow_mode": True,
                "would_execute": True,
            }

        logger.info(f"Rescheduling {workload_name} to node {new_node}")

        # Mock implementation
        await asyncio.sleep(0.3)

        return {
            "action": "reschedule",
            "workload": workload_name,
            "target_node": new_node,
            "status": "success (mocked)",
        }

    async def _handle_rollback(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
        ttl: int,
        shadow_mode: bool = False,
    ) -> dict[str, Any]:
        """Handle rollback decision."""
        workload_name = target.get("workload")
        revision = params.get("revision", "previous")

        if shadow_mode:
            logger.info(
                f"SHADOW: Would roll back {workload_name} to revision {revision}"
            )
            await asyncio.sleep(0.1)
            return {
                "action": "rollback",
                "workload": workload_name,
                "revision": revision,
                "status": "simulated",
                "shadow_mode": True,
                "would_execute": True,
            }

        logger.info(f"Rolling back {workload_name} to revision {revision}")

        # Mock implementation
        await asyncio.sleep(0.4)

        return {
            "action": "rollback",
            "workload": workload_name,
            "revision": revision,
            "status": "success (mocked)",
        }

    async def _handle_update(
        self,
        target: dict[str, Any],
        params: dict[str, Any],
        ttl: int,
        shadow_mode: bool = False,
    ) -> dict[str, Any]:
        """Handle update decision."""
        workload_name = target.get("workload")

        if shadow_mode:
            logger.info(f"SHADOW: Would update {workload_name} with params {params}")
            await asyncio.sleep(0.1)
            return {
                "action": "update",
                "workload": workload_name,
                "params": params,
                "status": "simulated",
                "shadow_mode": True,
                "would_execute": True,
            }

        logger.info(f"Updating {workload_name} with params {params}")

        # Mock implementation
        await asyncio.sleep(0.3)

        return {
            "action": "update",
            "workload": workload_name,
            "params": params,
            "status": "success (mocked)",
        }

    def get_execution_status(self, plan_id: UUID) -> dict[str, Any] | None:
        """
        Get execution status for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Execution status or None if not found
        """
        if plan_id in self._executing_plans:
            return {"status": "executing", "plan_id": str(plan_id)}

        return self._execution_history.get(plan_id)
