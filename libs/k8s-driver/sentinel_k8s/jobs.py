"""Kubernetes Job operations."""

from typing import Optional

from kubernetes.client import V1Job, V1JobSpec, V1ObjectMeta
from kubernetes.client import V1PodSpec, V1PodTemplateSpec
from kubernetes.client import V1Container, V1EnvVar, V1ResourceRequirements
from kubernetes.client.exceptions import ApiException
from tenacity import retry, stop_after_attempt, wait_exponential

from .cluster import ClusterConnection
from .models import JobSpec, ResourceStatus as ResourceStatusModel


class JobManager:
    """Manages Kubernetes Job operations."""

    def __init__(self, cluster: ClusterConnection):
        """
        Initialize job manager.

        Args:
            cluster: Cluster connection
        """
        self.cluster = cluster
        self.batch_v1 = cluster.batch_v1

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def create(self, spec: JobSpec) -> V1Job:
        """
        Create a job.

        Args:
            spec: Job specification

        Returns:
            Created V1Job

        Raises:
            ApiException: If creation fails
        """
        # Build container spec
        container = V1Container(
            name=spec.name,
            image=spec.image,
            command=spec.command,
            args=spec.args,
            env=[V1EnvVar(name=k, value=v) for k, v in spec.env.items()],
        )

        # Add resource requirements if specified
        if spec.resources:
            container.resources = V1ResourceRequirements(**spec.resources)

        # Build pod spec
        pod_spec = V1PodSpec(
            containers=[container],
            restart_policy="OnFailure",
        )

        # Add Sentinel labels
        labels = {
            "app": "sentinel",
            "managed-by": "sentinel",
            "workload": spec.name,
            **spec.labels,
        }

        # Build job
        job = V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=V1ObjectMeta(
                name=spec.name,
                namespace=spec.namespace,
                labels=labels,
                annotations=spec.annotations,
            ),
            spec=V1JobSpec(
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(labels=labels),
                    spec=pod_spec,
                ),
                backoff_limit=spec.backoff_limit,
                ttl_seconds_after_finished=spec.ttl_seconds_after_finished,
                parallelism=spec.parallelism,
                completions=spec.completions,
            ),
        )

        return self.batch_v1.create_namespaced_job(
            namespace=spec.namespace,
            body=job,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get(self, name: str, namespace: str = "default") -> Optional[V1Job]:
        """
        Get a job.

        Args:
            name: Job name
            namespace: Kubernetes namespace

        Returns:
            V1Job or None if not found
        """
        try:
            return self.batch_v1.read_namespaced_job(name, namespace)
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def delete(self, name: str, namespace: str = "default") -> bool:
        """
        Delete a job.

        Args:
            name: Job name
            namespace: Kubernetes namespace

        Returns:
            True if deleted, False if not found

        Raises:
            ApiException: If deletion fails
        """
        try:
            self.batch_v1.delete_namespaced_job(
                name,
                namespace,
                propagation_policy="Background",
            )
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def get_status(
        self, name: str, namespace: str = "default"
    ) -> Optional[ResourceStatusModel]:
        """
        Get job status.

        Args:
            name: Job name
            namespace: Kubernetes namespace

        Returns:
            ResourceStatus or None if not found
        """
        job = self.get(name, namespace)
        if not job:
            return None

        status = job.status
        conditions = []
        if status.conditions:
            conditions = [
                {
                    "type": c.type,
                    "status": c.status,
                    "reason": c.reason,
                    "message": c.message,
                }
                for c in status.conditions
            ]

        # Determine overall status
        if status.succeeded and status.succeeded > 0:
            overall_status = "completed"
        elif status.failed and status.failed >= job.spec.backoff_limit:
            overall_status = "failed"
        elif status.active and status.active > 0:
            overall_status = "running"
        else:
            overall_status = "pending"

        # Build status message
        message = None
        if status.succeeded:
            message = f"Job completed successfully ({status.succeeded} pods)"
        elif status.failed:
            message = f"Job failed ({status.failed} pods failed)"
        elif status.active:
            message = f"Job running ({status.active} active pods)"

        return ResourceStatusModel(
            name=name,
            namespace=namespace,
            kind="Job",
            status=overall_status,
            conditions=conditions,
            created_at=job.metadata.creation_timestamp,
            message=message,
        )

    def list(
        self, namespace: str = "default", labels: Optional[dict[str, str]] = None
    ) -> list[V1Job]:
        """
        List jobs.

        Args:
            namespace: Kubernetes namespace
            labels: Label selector dict

        Returns:
            List of V1Job objects
        """
        label_selector = None
        if labels:
            label_selector = ",".join([f"{k}={v}" for k, v in labels.items()])

        result = self.batch_v1.list_namespaced_job(
            namespace=namespace,
            label_selector=label_selector,
        )
        return result.items

    def get_logs(self, name: str, namespace: str = "default") -> Optional[str]:
        """
        Get logs from job pods.

        Args:
            name: Job name
            namespace: Kubernetes namespace

        Returns:
            Combined logs from all job pods or None if no pods found
        """
        # List pods for this job
        pods = self.cluster.core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=f"job-name={name}",
        )

        if not pods.items:
            return None

        logs = []
        for pod in pods.items:
            try:
                pod_logs = self.cluster.core_v1.read_namespaced_pod_log(
                    name=pod.metadata.name,
                    namespace=namespace,
                )
                logs.append(f"=== Pod: {pod.metadata.name} ===\n{pod_logs}")
            except ApiException:
                logs.append(f"=== Pod: {pod.metadata.name} ===\nLogs not available")

        return "\n\n".join(logs)
