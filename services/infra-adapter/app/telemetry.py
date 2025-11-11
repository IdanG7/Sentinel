"""Telemetry collection from Prometheus."""

import logging
from datetime import datetime
from typing import Any

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class TelemetryCollector:
    """
    Collects telemetry metrics from Prometheus.
    """

    def __init__(self, settings: Settings):
        """
        Initialize telemetry collector.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.prometheus_url = settings.prometheus_url
        self.query_range = settings.telemetry_query_range_seconds

        # Define metrics to collect
        self.metrics_queries = {
            # Node metrics
            "node_cpu_usage": "avg(sentinel_node_cpu_percent) by (node)",
            "node_memory_usage": 'avg(sentinel_node_memory_bytes{type="used"}) by (node)',
            "node_gpu_utilization": "avg(sentinel_node_gpu_utilization_percent) by (node, gpu_index)",
            # Workload metrics
            "workload_latency_p99": "histogram_quantile(0.99, sum(rate(sentinel_workload_inference_latency_ms_bucket[5m])) by (workload, le))",
            "workload_success_rate": 'sum(rate(sentinel_workload_requests_total{status="success"}[5m])) by (workload) / sum(rate(sentinel_workload_requests_total[5m])) by (workload)',
            "workload_queue_depth": "sentinel_workload_queue_depth",
            # Deployment metrics
            "deployment_replicas_available": 'kube_deployment_status_replicas_available{app="sentinel"}',
            "deployment_replicas_desired": 'kube_deployment_spec_replicas{app="sentinel"}',
            # System metrics
            "http_request_rate": "sum(rate(http_requests_total[5m])) by (endpoint)",
            "http_error_rate": 'sum(rate(http_requests_total{status=~"5.."}[5m])) by (endpoint)',
        }

    async def collect(self) -> list[dict[str, Any]]:
        """
        Collect telemetry from Prometheus.

        Returns:
            List of telemetry data points
        """
        telemetry_points = []
        timestamp = datetime.utcnow()

        async with httpx.AsyncClient() as client:
            for metric_name, query in self.metrics_queries.items():
                try:
                    # Query Prometheus
                    response = await client.get(
                        f"{self.prometheus_url}/api/v1/query",
                        params={"query": query},
                        timeout=10.0,
                    )

                    if response.status_code != 200:
                        logger.warning(
                            f"Prometheus query failed for {metric_name}: {response.status_code}"
                        )
                        continue

                    data = response.json()

                    if data.get("status") != "success":
                        logger.warning(f"Prometheus query unsuccessful for {metric_name}")
                        continue

                    # Parse results
                    results = data.get("data", {}).get("result", [])

                    for result in results:
                        metric_labels = result.get("metric", {})
                        value = result.get("value", [None, None])[1]

                        if value is None:
                            continue

                        # Create telemetry point
                        telemetry_point = {
                            "timestamp": timestamp.isoformat(),
                            "type": "metric",
                            "metric_name": metric_name,
                            "value": float(value),
                            "labels": metric_labels,
                        }

                        telemetry_points.append(telemetry_point)

                except Exception as e:
                    logger.error(f"Error collecting {metric_name}: {e}", exc_info=True)

        logger.debug(f"Collected {len(telemetry_points)} telemetry points")
        return telemetry_points

    async def collect_range(
        self, start: datetime, end: datetime, step: int = 60
    ) -> list[dict[str, Any]]:
        """
        Collect telemetry for a time range.

        Args:
            start: Start timestamp
            end: End timestamp
            step: Step size in seconds

        Returns:
            List of telemetry data points
        """
        telemetry_points = []

        async with httpx.AsyncClient() as client:
            for metric_name, query in self.metrics_queries.items():
                try:
                    # Query Prometheus range
                    response = await client.get(
                        f"{self.prometheus_url}/api/v1/query_range",
                        params={
                            "query": query,
                            "start": int(start.timestamp()),
                            "end": int(end.timestamp()),
                            "step": step,
                        },
                        timeout=30.0,
                    )

                    if response.status_code != 200:
                        logger.warning(f"Prometheus range query failed for {metric_name}")
                        continue

                    data = response.json()

                    if data.get("status") != "success":
                        continue

                    # Parse results
                    results = data.get("data", {}).get("result", [])

                    for result in results:
                        metric_labels = result.get("metric", {})
                        values = result.get("values", [])

                        for timestamp, value in values:
                            if value is None:
                                continue

                            telemetry_point = {
                                "timestamp": datetime.fromtimestamp(timestamp).isoformat(),
                                "type": "metric",
                                "metric_name": metric_name,
                                "value": float(value),
                                "labels": metric_labels,
                            }

                            telemetry_points.append(telemetry_point)

                except Exception as e:
                    logger.error(f"Error collecting range for {metric_name}: {e}", exc_info=True)

        return telemetry_points
