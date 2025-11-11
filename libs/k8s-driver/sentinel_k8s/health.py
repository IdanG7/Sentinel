"""Health check framework for Kubernetes deployments."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from kubernetes.client import V1Deployment, V1Pod
from kubernetes.client.exceptions import ApiException

from .cluster import ClusterConnection


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus
    message: str
    checked_at: datetime
    details: dict[str, Any]
    score: float  # 0.0 (unhealthy) to 1.0 (healthy)


class DeploymentHealthChecker:
    """
    Health checker for Kubernetes deployments.

    Evaluates deployment health based on multiple criteria:
    - Replica availability
    - Pod readiness
    - Pod restarts
    - Image pull errors
    - CrashLoopBackOff status
    """

    def __init__(self, cluster: ClusterConnection):
        """
        Initialize health checker.

        Args:
            cluster: Cluster connection
        """
        self.cluster = cluster
        self.apps_v1 = cluster.apps_v1
        self.core_v1 = cluster.core_v1

    def check_deployment_health(
        self,
        name: str,
        namespace: str = "default",
        min_ready_percentage: float = 0.8,
        max_restart_count: int = 5,
    ) -> HealthCheckResult:
        """
        Check overall health of a deployment.

        Args:
            name: Deployment name
            namespace: Kubernetes namespace
            min_ready_percentage: Minimum percentage of ready replicas (0.0-1.0)
            max_restart_count: Maximum allowed pod restart count

        Returns:
            HealthCheckResult with overall health status
        """
        checked_at = datetime.utcnow()
        details: dict[str, Any] = {}
        issues: list[str] = []
        score = 1.0

        try:
            # Get deployment
            deployment = self.apps_v1.read_namespaced_deployment(name, namespace)
            details["deployment"] = {
                "name": name,
                "namespace": namespace,
                "replicas": deployment.spec.replicas,
                "ready_replicas": deployment.status.ready_replicas or 0,
                "available_replicas": deployment.status.available_replicas or 0,
                "updated_replicas": deployment.status.updated_replicas or 0,
            }

            # Check replica availability
            desired_replicas = deployment.spec.replicas or 0
            ready_replicas = deployment.status.ready_replicas or 0
            available_replicas = deployment.status.available_replicas or 0

            if desired_replicas == 0:
                issues.append("Deployment scaled to zero replicas")
                score *= 0.5
            else:
                ready_percentage = ready_replicas / desired_replicas
                available_percentage = available_replicas / desired_replicas

                details["ready_percentage"] = ready_percentage
                details["available_percentage"] = available_percentage

                if ready_percentage < min_ready_percentage:
                    issues.append(
                        f"Only {ready_percentage:.0%} of replicas are ready "
                        f"(minimum: {min_ready_percentage:.0%})"
                    )
                    score *= ready_percentage

                if available_percentage < min_ready_percentage:
                    issues.append(
                        f"Only {available_percentage:.0%} of replicas are available"
                    )
                    score *= 0.9

            # Get pods for this deployment
            label_selector = f"workload={name}"
            pods = self.core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )

            # Check pod health
            pod_issues = self._check_pod_health(pods.items, max_restart_count)
            if pod_issues:
                issues.extend(pod_issues)
                score *= 0.8

            details["pod_count"] = len(pods.items)
            details["issues"] = issues

            # Determine overall status
            if score >= 0.9:
                status = HealthStatus.HEALTHY
                message = "Deployment is healthy"
            elif score >= 0.6:
                status = HealthStatus.DEGRADED
                message = f"Deployment is degraded: {'; '.join(issues)}"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Deployment is unhealthy: {'; '.join(issues)}"

        except ApiException as e:
            if e.status == 404:
                status = HealthStatus.UNKNOWN
                message = f"Deployment {name} not found"
                score = 0.0
            else:
                status = HealthStatus.UNKNOWN
                message = f"Error checking deployment health: {e.reason}"
                score = 0.0
            details["error"] = str(e)

        except Exception as e:
            status = HealthStatus.UNKNOWN
            message = f"Unexpected error checking health: {str(e)}"
            score = 0.0
            details["error"] = str(e)

        return HealthCheckResult(
            status=status,
            message=message,
            checked_at=checked_at,
            details=details,
            score=score,
        )

    def _check_pod_health(self, pods: list[V1Pod], max_restart_count: int) -> list[str]:
        """
        Check health of individual pods.

        Args:
            pods: List of pods to check
            max_restart_count: Maximum allowed restart count

        Returns:
            List of issues found
        """
        issues: list[str] = []

        for pod in pods:
            pod_name = pod.metadata.name
            phase = pod.status.phase

            # Check pod phase
            if phase not in ["Running", "Succeeded"]:
                issues.append(f"Pod {pod_name} in {phase} phase")

            # Check container statuses
            if pod.status.container_statuses:
                for container_status in pod.status.container_statuses:
                    container_name = container_status.name

                    # Check restart count
                    restart_count = container_status.restart_count
                    if restart_count > max_restart_count:
                        issues.append(
                            f"Container {container_name} in pod {pod_name} "
                            f"has {restart_count} restarts (max: {max_restart_count})"
                        )

                    # Check waiting state
                    if container_status.state and container_status.state.waiting:
                        reason = container_status.state.waiting.reason
                        if reason in [
                            "CrashLoopBackOff",
                            "ImagePullBackOff",
                            "ErrImagePull",
                        ]:
                            issues.append(
                                f"Container {container_name} in pod {pod_name} "
                                f"is in {reason} state"
                            )

                    # Check readiness
                    if not container_status.ready:
                        issues.append(
                            f"Container {container_name} in pod {pod_name} is not ready"
                        )

        return issues

    def wait_for_healthy(
        self,
        name: str,
        namespace: str = "default",
        timeout_seconds: int = 300,
        check_interval_seconds: int = 10,
        min_ready_percentage: float = 0.8,
    ) -> HealthCheckResult:
        """
        Wait for deployment to become healthy.

        Args:
            name: Deployment name
            namespace: Kubernetes namespace
            timeout_seconds: Maximum time to wait
            check_interval_seconds: Time between health checks
            min_ready_percentage: Minimum percentage of ready replicas

        Returns:
            HealthCheckResult when healthy or timeout reached
        """
        import time

        start_time = time.time()

        while (time.time() - start_time) < timeout_seconds:
            result = self.check_deployment_health(
                name, namespace, min_ready_percentage=min_ready_percentage
            )

            if result.status == HealthStatus.HEALTHY:
                return result

            if result.status == HealthStatus.UNKNOWN:
                # Deployment not found or error - stop waiting
                return result

            time.sleep(check_interval_seconds)

        # Timeout reached
        result = self.check_deployment_health(
            name, namespace, min_ready_percentage=min_ready_percentage
        )
        if result.status != HealthStatus.HEALTHY:
            result.details["timeout"] = True
            result.message += f" (timeout after {timeout_seconds}s)"

        return result
