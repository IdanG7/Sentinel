"""Kubernetes watch and reconciliation functionality."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Callable, Optional

from kubernetes import watch as k8s_watch
from kubernetes.client.exceptions import ApiException

from .cluster import ClusterConnection
from .models import WatchEvent

logger = logging.getLogger(__name__)


class ResourceWatcher:
    """Watches Kubernetes resources for changes."""

    def __init__(self, cluster: ClusterConnection):
        """
        Initialize resource watcher.

        Args:
            cluster: Cluster connection
        """
        self.cluster = cluster
        self.core_v1 = cluster.core_v1
        self.apps_v1 = cluster.apps_v1
        self.batch_v1 = cluster.batch_v1
        self._watch = k8s_watch.Watch()
        self._handlers: dict[str, list[Callable]] = {}

    def register_handler(
        self,
        resource_type: str,
        handler: Callable[[WatchEvent], None],
    ) -> None:
        """
        Register a handler for watch events.

        Args:
            resource_type: Type of resource (deployment, job, statefulset, pod)
            handler: Callback function that takes WatchEvent
        """
        if resource_type not in self._handlers:
            self._handlers[resource_type] = []
        self._handlers[resource_type].append(handler)

    def _emit_event(self, event: WatchEvent) -> None:
        """
        Emit a watch event to registered handlers.

        Args:
            event: Watch event to emit
        """
        handlers = self._handlers.get(event.resource_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in watch event handler: {e}", exc_info=True)

    def watch_deployments(
        self,
        namespace: str = "default",
        label_selector: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        Watch deployments for changes.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector string (e.g., "app=sentinel")
            timeout_seconds: Watch timeout in seconds (None for infinite)
        """
        try:
            logger.info(f"Starting watch on deployments in namespace {namespace}")
            for event in self._watch.stream(
                self.apps_v1.list_namespaced_deployment,
                namespace=namespace,
                label_selector=label_selector,
                timeout_seconds=timeout_seconds,
            ):
                obj = event["object"]
                watch_event = WatchEvent(
                    event_type=event["type"],
                    resource_type="deployment",
                    name=obj.metadata.name,
                    namespace=obj.metadata.namespace,
                    object=obj.to_dict(),
                    timestamp=datetime.utcnow(),
                )
                self._emit_event(watch_event)
        except ApiException as e:
            if e.status == 410:  # Resource version too old
                logger.warning("Watch expired, restarting...")
                self.watch_deployments(namespace, label_selector, timeout_seconds)
            else:
                logger.error(f"Error watching deployments: {e}", exc_info=True)
                raise

    def watch_jobs(
        self,
        namespace: str = "default",
        label_selector: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        Watch jobs for changes.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector string
            timeout_seconds: Watch timeout in seconds
        """
        try:
            logger.info(f"Starting watch on jobs in namespace {namespace}")
            for event in self._watch.stream(
                self.batch_v1.list_namespaced_job,
                namespace=namespace,
                label_selector=label_selector,
                timeout_seconds=timeout_seconds,
            ):
                obj = event["object"]
                watch_event = WatchEvent(
                    event_type=event["type"],
                    resource_type="job",
                    name=obj.metadata.name,
                    namespace=obj.metadata.namespace,
                    object=obj.to_dict(),
                    timestamp=datetime.utcnow(),
                )
                self._emit_event(watch_event)
        except ApiException as e:
            if e.status == 410:
                logger.warning("Watch expired, restarting...")
                self.watch_jobs(namespace, label_selector, timeout_seconds)
            else:
                logger.error(f"Error watching jobs: {e}", exc_info=True)
                raise

    def watch_statefulsets(
        self,
        namespace: str = "default",
        label_selector: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        Watch statefulsets for changes.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector string
            timeout_seconds: Watch timeout in seconds
        """
        try:
            logger.info(f"Starting watch on statefulsets in namespace {namespace}")
            for event in self._watch.stream(
                self.apps_v1.list_namespaced_stateful_set,
                namespace=namespace,
                label_selector=label_selector,
                timeout_seconds=timeout_seconds,
            ):
                obj = event["object"]
                watch_event = WatchEvent(
                    event_type=event["type"],
                    resource_type="statefulset",
                    name=obj.metadata.name,
                    namespace=obj.metadata.namespace,
                    object=obj.to_dict(),
                    timestamp=datetime.utcnow(),
                )
                self._emit_event(watch_event)
        except ApiException as e:
            if e.status == 410:
                logger.warning("Watch expired, restarting...")
                self.watch_statefulsets(namespace, label_selector, timeout_seconds)
            else:
                logger.error(f"Error watching statefulsets: {e}", exc_info=True)
                raise

    def watch_pods(
        self,
        namespace: str = "default",
        label_selector: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ) -> None:
        """
        Watch pods for changes.

        Args:
            namespace: Kubernetes namespace
            label_selector: Label selector string
            timeout_seconds: Watch timeout in seconds
        """
        try:
            logger.info(f"Starting watch on pods in namespace {namespace}")
            for event in self._watch.stream(
                self.core_v1.list_namespaced_pod,
                namespace=namespace,
                label_selector=label_selector,
                timeout_seconds=timeout_seconds,
            ):
                obj = event["object"]
                watch_event = WatchEvent(
                    event_type=event["type"],
                    resource_type="pod",
                    name=obj.metadata.name,
                    namespace=obj.metadata.namespace,
                    object=obj.to_dict(),
                    timestamp=datetime.utcnow(),
                )
                self._emit_event(watch_event)
        except ApiException as e:
            if e.status == 410:
                logger.warning("Watch expired, restarting...")
                self.watch_pods(namespace, label_selector, timeout_seconds)
            else:
                logger.error(f"Error watching pods: {e}", exc_info=True)
                raise

    def stop(self) -> None:
        """Stop all active watches."""
        self._watch.stop()


class ReconciliationLoop(ABC):
    """
    Base class for reconciliation loops.

    Implements the standard Kubernetes operator pattern:
    1. Watch for resource changes
    2. Reconcile desired state with actual state
    3. Update status
    """

    def __init__(
        self,
        cluster: ClusterConnection,
        namespace: str = "default",
        reconcile_interval: int = 30,
    ):
        """
        Initialize reconciliation loop.

        Args:
            cluster: Cluster connection
            namespace: Kubernetes namespace to watch
            reconcile_interval: Interval between reconciliation runs (seconds)
        """
        self.cluster = cluster
        self.namespace = namespace
        self.reconcile_interval = reconcile_interval
        self.watcher = ResourceWatcher(cluster)
        self._running = False
        self._tasks: list[asyncio.Task] = []

    @abstractmethod
    async def reconcile(self, event: WatchEvent) -> None:
        """
        Reconcile a resource based on a watch event.

        Args:
            event: Watch event that triggered reconciliation
        """
        pass

    @abstractmethod
    def get_label_selector(self) -> str:
        """
        Get the label selector for watching resources.

        Returns:
            Label selector string (e.g., "managed-by=sentinel")
        """
        pass

    def _handle_event(self, event: WatchEvent) -> None:
        """
        Handle a watch event by scheduling reconciliation.

        Args:
            event: Watch event
        """
        if not self._running:
            return

        logger.info(
            f"Received {event.event_type} event for {event.resource_type} "
            f"{event.namespace}/{event.name}"
        )

        # Schedule reconciliation in the event loop
        asyncio.create_task(self._safe_reconcile(event))

    async def _safe_reconcile(self, event: WatchEvent) -> None:
        """
        Safely execute reconciliation with error handling.

        Args:
            event: Watch event
        """
        try:
            await self.reconcile(event)
        except Exception as e:
            logger.error(
                f"Error reconciling {event.resource_type} "
                f"{event.namespace}/{event.name}: {e}",
                exc_info=True,
            )

    async def _periodic_reconcile(self) -> None:
        """Run periodic reconciliation for all resources."""
        while self._running:
            try:
                await asyncio.sleep(self.reconcile_interval)
                logger.debug("Running periodic reconciliation")
                # Subclasses can override this to implement periodic reconciliation
                await self.periodic_reconcile()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic reconciliation: {e}", exc_info=True)

    async def periodic_reconcile(self) -> None:
        """
        Override this method to implement periodic reconciliation.

        This is called at regular intervals defined by reconcile_interval.
        """
        pass

    async def start(self) -> None:
        """Start the reconciliation loop."""
        if self._running:
            logger.warning("Reconciliation loop already running")
            return

        self._running = True
        label_selector = self.get_label_selector()

        logger.info(
            f"Starting reconciliation loop for namespace {self.namespace} "
            f"with label selector: {label_selector}"
        )

        # Register watch handlers
        self.watcher.register_handler(self.get_resource_type(), self._handle_event)

        # Start watch in background task
        watch_method = getattr(self.watcher, f"watch_{self.get_resource_type()}s")
        watch_task = asyncio.create_task(
            asyncio.to_thread(
                watch_method,
                namespace=self.namespace,
                label_selector=label_selector,
            )
        )
        self._tasks.append(watch_task)

        # Start periodic reconciliation
        periodic_task = asyncio.create_task(self._periodic_reconcile())
        self._tasks.append(periodic_task)

    async def stop(self) -> None:
        """Stop the reconciliation loop."""
        logger.info("Stopping reconciliation loop")
        self._running = False
        self.watcher.stop()

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    @abstractmethod
    def get_resource_type(self) -> str:
        """
        Get the resource type to watch.

        Returns:
            Resource type string (deployment, job, statefulset, pod)
        """
        pass
