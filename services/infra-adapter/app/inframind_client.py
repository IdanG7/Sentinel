"""InfraMind Client - Integration with InfraMind decision brain."""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class InfraMindDecisionClient:
    """
    Client for InfraMind decision brain.

    This client sends telemetry to InfraMind and receives intelligent
    action plans based on ML-powered analysis.
    """

    def __init__(self, base_url: str, api_key: str | None = None):
        """
        Initialize InfraMind client.

        Args:
            base_url: InfraMind API base URL (e.g., http://inframind:8081)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        """Initialize HTTP client."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )
        logger.info(f"InfraMind client connected to {self.base_url}")

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("InfraMind client disconnected")

    async def send_telemetry(self, telemetry_batch: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Send telemetry batch to InfraMind.

        Args:
            telemetry_batch: List of telemetry data points

        Returns:
            Response from InfraMind with acknowledgment
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        logger.info(f"Sending {len(telemetry_batch)} telemetry points to InfraMind")

        try:
            response = await self._client.post(
                "/api/telemetry",
                json={"batch": telemetry_batch},
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"✓ Telemetry sent successfully: {result.get('message', 'OK')}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to send telemetry: {e}")
            raise

    async def get_optimization_suggestions(
        self,
        cluster_id: str,
        context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        Get optimization suggestions from InfraMind.

        Args:
            cluster_id: Cluster identifier
            context: Optional context information (workload state, metrics, etc.)

        Returns:
            List of action plan decisions
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        logger.info(f"Requesting optimization suggestions for cluster {cluster_id}")

        try:
            payload = {
                "cluster_id": cluster_id,
                "context": context or {},
            }

            response = await self._client.post(
                "/api/optimize",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            decisions = result.get("decisions", [])
            logger.info(
                f"✓ Received {len(decisions)} optimization suggestions "
                f"(confidence: {result.get('confidence', 0.0):.2f})"
            )

            return decisions

        except httpx.HTTPError as e:
            logger.error(f"Failed to get optimization suggestions: {e}")
            raise

    async def report_execution_outcome(
        self,
        plan_id: str,
        success: bool,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """
        Report execution outcome back to InfraMind for learning.

        Args:
            plan_id: Action plan ID
            success: Whether execution succeeded
            metrics: Optional execution metrics (duration, resource usage, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not connected. Call connect() first.")

        logger.info(f"Reporting execution outcome for plan {plan_id}: {success}")

        try:
            payload = {
                "plan_id": plan_id,
                "success": success,
                "metrics": metrics or {},
            }

            response = await self._client.post(
                "/api/feedback",
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"✓ Execution outcome reported for plan {plan_id}")

        except httpx.HTTPError as e:
            logger.error(f"Failed to report execution outcome: {e}")
            # Don't raise - feedback is best-effort
