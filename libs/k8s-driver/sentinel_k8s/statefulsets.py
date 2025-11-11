"""Kubernetes StatefulSet operations."""

from typing import Optional

from kubernetes.client import V1StatefulSet, V1StatefulSetSpec, V1LabelSelector
from kubernetes.client import V1ObjectMeta, V1PodSpec, V1PodTemplateSpec
from kubernetes.client import V1Container, V1ContainerPort, V1EnvVar
from kubernetes.client import V1ResourceRequirements, V1PersistentVolumeClaim
from kubernetes.client.exceptions import ApiException
from tenacity import retry, stop_after_attempt, wait_exponential

from .cluster import ClusterConnection
from .models import StatefulSetSpec, ResourceStatus as ResourceStatusModel


class StatefulSetManager:
    """Manages Kubernetes StatefulSet operations."""

    def __init__(self, cluster: ClusterConnection):
        """
        Initialize statefulset manager.

        Args:
            cluster: Cluster connection
        """
        self.cluster = cluster
        self.apps_v1 = cluster.apps_v1

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def create(self, spec: StatefulSetSpec) -> V1StatefulSet:
        """
        Create a statefulset.

        Args:
            spec: StatefulSet specification

        Returns:
            Created V1StatefulSet

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
            ports=[V1ContainerPort(**port) for port in spec.ports],
        )

        # Add resource requirements if specified
        if spec.resources:
            container.resources = V1ResourceRequirements(**spec.resources)

        # Build pod spec
        pod_spec = V1PodSpec(
            containers=[container],
        )

        # Add Sentinel labels
        labels = {
            "app": "sentinel",
            "managed-by": "sentinel",
            "workload": spec.name,
            **spec.labels,
        }

        # Build volume claim templates if specified
        volume_claim_templates = None
        if spec.volume_claim_templates:
            volume_claim_templates = [
                V1PersistentVolumeClaim(**vct) for vct in spec.volume_claim_templates
            ]

        # Build statefulset
        statefulset = V1StatefulSet(
            api_version="apps/v1",
            kind="StatefulSet",
            metadata=V1ObjectMeta(
                name=spec.name,
                namespace=spec.namespace,
                labels=labels,
                annotations=spec.annotations,
            ),
            spec=V1StatefulSetSpec(
                replicas=spec.replicas,
                service_name=spec.service_name,
                selector=V1LabelSelector(match_labels={"workload": spec.name}),
                template=V1PodTemplateSpec(
                    metadata=V1ObjectMeta(labels=labels),
                    spec=pod_spec,
                ),
                volume_claim_templates=volume_claim_templates,
            ),
        )

        return self.apps_v1.create_namespaced_stateful_set(
            namespace=spec.namespace,
            body=statefulset,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def get(self, name: str, namespace: str = "default") -> Optional[V1StatefulSet]:
        """
        Get a statefulset.

        Args:
            name: StatefulSet name
            namespace: Kubernetes namespace

        Returns:
            V1StatefulSet or None if not found
        """
        try:
            return self.apps_v1.read_namespaced_stateful_set(name, namespace)
        except ApiException as e:
            if e.status == 404:
                return None
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def update(self, name: str, namespace: str, spec: StatefulSetSpec) -> V1StatefulSet:
        """
        Update an existing statefulset.

        Args:
            name: StatefulSet name
            namespace: Kubernetes namespace
            spec: Updated statefulset specification

        Returns:
            Updated V1StatefulSet

        Raises:
            ApiException: If update fails
        """
        # Get existing statefulset
        existing = self.get(name, namespace)
        if not existing:
            raise ValueError(f"StatefulSet {name} not found in namespace {namespace}")

        # Update container image and env
        existing.spec.template.spec.containers[0].image = spec.image
        existing.spec.template.spec.containers[0].env = [
            V1EnvVar(name=k, value=v) for k, v in spec.env.items()
        ]

        # Update replicas
        existing.spec.replicas = spec.replicas

        # Update labels and annotations
        existing.metadata.labels.update(spec.labels)
        existing.metadata.annotations.update(spec.annotations)

        return self.apps_v1.replace_namespaced_stateful_set(
            name=name,
            namespace=namespace,
            body=existing,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def scale(self, name: str, namespace: str, replicas: int) -> V1StatefulSet:
        """
        Scale a statefulset.

        Args:
            name: StatefulSet name
            namespace: Kubernetes namespace
            replicas: Target replica count

        Returns:
            Scaled V1StatefulSet

        Raises:
            ApiException: If scaling fails
        """
        # Patch the statefulset
        patch = {"spec": {"replicas": replicas}}
        return self.apps_v1.patch_namespaced_stateful_set_scale(
            name=name,
            namespace=namespace,
            body=patch,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def delete(self, name: str, namespace: str = "default") -> bool:
        """
        Delete a statefulset.

        Args:
            name: StatefulSet name
            namespace: Kubernetes namespace

        Returns:
            True if deleted, False if not found

        Raises:
            ApiException: If deletion fails
        """
        try:
            self.apps_v1.delete_namespaced_stateful_set(name, namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def get_status(
        self, name: str, namespace: str = "default"
    ) -> Optional[ResourceStatusModel]:
        """
        Get statefulset status.

        Args:
            name: StatefulSet name
            namespace: Kubernetes namespace

        Returns:
            ResourceStatus or None if not found
        """
        statefulset = self.get(name, namespace)
        if not statefulset:
            return None

        status = statefulset.status
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
        if status.ready_replicas == statefulset.spec.replicas:
            overall_status = "running"
        elif status.replicas is None or status.replicas == 0:
            overall_status = "pending"
        elif (
            status.ready_replicas and status.ready_replicas < statefulset.spec.replicas
        ):
            overall_status = "scaling"
        elif status.current_replicas != status.updated_replicas:
            overall_status = "updating"
        else:
            overall_status = "unknown"

        return ResourceStatusModel(
            name=name,
            namespace=namespace,
            kind="StatefulSet",
            status=overall_status,
            replicas=status.replicas,
            ready_replicas=status.ready_replicas,
            available_replicas=status.available_replicas,
            conditions=conditions,
            created_at=statefulset.metadata.creation_timestamp,
        )

    def list(
        self, namespace: str = "default", labels: Optional[dict[str, str]] = None
    ) -> list[V1StatefulSet]:
        """
        List statefulsets.

        Args:
            namespace: Kubernetes namespace
            labels: Label selector dict

        Returns:
            List of V1StatefulSet objects
        """
        label_selector = None
        if labels:
            label_selector = ",".join([f"{k}={v}" for k, v in labels.items()])

        result = self.apps_v1.list_namespaced_stateful_set(
            namespace=namespace,
            label_selector=label_selector,
        )
        return result.items
