"""
Locust load testing for Sentinel Control API.

Run with:
    locust -f tests/load/locustfile.py --host=http://localhost:8000

Or headless:
    locust -f tests/load/locustfile.py --host=http://localhost:8000 \
           --users=100 --spawn-rate=10 --run-time=10m --headless
"""

import json
import random
import uuid
from datetime import datetime

from locust import HttpUser, between, task


class SentinelUser(HttpUser):
    """
    Simulates a Sentinel operator/system user.

    Tests realistic workflows:
    - View workloads and deployments (read-heavy)
    - Submit action plans (write operations)
    - Query metrics and audits
    - Create/update policies
    """

    wait_time = between(1, 5)  # Wait 1-5s between tasks

    def on_start(self):
        """Called when a simulated user starts."""
        # Authenticate (in production, get JWT token)
        self.client.headers = {
            "Authorization": "Bearer test-operator-token",
            "Content-Type": "application/json",
        }

        # Track created resources for cleanup
        self.workload_ids = []
        self.deployment_ids = []
        self.plan_ids = []

    @task(10)
    def list_workloads(self):
        """List all workloads (most common operation)."""
        with self.client.get(
            "/api/v1/workloads",
            catch_response=True,
            name="GET /workloads",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(8)
    def list_deployments(self):
        """List all deployments."""
        with self.client.get(
            "/api/v1/deployments",
            catch_response=True,
            name="GET /deployments",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(5)
    def get_deployment_status(self):
        """Get status of a specific deployment."""
        if self.deployment_ids:
            deployment_id = random.choice(self.deployment_ids)
            with self.client.get(
                f"/api/v1/deployments/{deployment_id}",
                catch_response=True,
                name="GET /deployments/:id",
            ) as response:
                if response.status_code in (200, 404):
                    response.success()
                else:
                    response.failure(f"Got status {response.status_code}")

    @task(3)
    def create_workload(self):
        """Create a new workload."""
        workload_name = f"load-test-{uuid.uuid4().hex[:8]}"

        payload = {
            "name": workload_name,
            "type": random.choice(["training", "inference", "batch"]),
            "image": "ghcr.io/sentinel/test:latest",
            "resources": {
                "cpu": str(random.choice([2, 4, 8])),
                "memory": f"{random.choice([4, 8, 16])}Gi",
                "gpu": {"count": random.choice([0, 1, 2]), "sku": "L4"},
            },
        }

        with self.client.post(
            "/api/v1/workloads",
            json=payload,
            catch_response=True,
            name="POST /workloads",
        ) as response:
            if response.status_code == 201:
                data = response.json()
                self.workload_ids.append(data.get("id"))
                response.success()
            elif response.status_code == 409:
                # Conflict (already exists) is acceptable
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(2)
    def submit_action_plan(self):
        """Submit an action plan (scale operation)."""
        plan_id = str(uuid.uuid4())

        payload = {
            "plan_id": plan_id,
            "source": "load-test",
            "decisions": [
                {
                    "verb": "scale",
                    "target": {
                        "deploymentId": random.choice(self.deployment_ids)
                        if self.deployment_ids
                        else "test-deployment"
                    },
                    "params": {"replicas": random.randint(1, 10)},
                    "ttl": 300,
                    "safety": {"rate_limit": 5, "window": "1m"},
                }
            ],
            "created_at": datetime.utcnow().isoformat(),
        }

        with self.client.post(
            "/api/v1/action-plans",
            json=payload,
            catch_response=True,
            name="POST /action-plans",
        ) as response:
            if response.status_code in (200, 201, 202):
                self.plan_ids.append(plan_id)
                response.success()
            elif response.status_code == 429:
                # Rate limited is expected under load
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(4)
    def query_audits(self):
        """Query audit logs."""
        params = {
            "limit": 50,
            "offset": random.randint(0, 1000),
        }

        with self.client.get(
            "/api/v1/audits",
            params=params,
            catch_response=True,
            name="GET /audits",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(3)
    def list_policies(self):
        """List policies."""
        with self.client.get(
            "/api/v1/policies",
            catch_response=True,
            name="GET /policies",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(1)
    def create_policy(self):
        """Create a policy (admin operation)."""
        policy_name = f"policy-{uuid.uuid4().hex[:8]}"

        payload = {
            "name": policy_name,
            "rules": [
                {
                    "type": "cost_ceiling",
                    "selector": {"tenant": "load-test"},
                    "constraint": {"max_cost_per_hour": 100.0},
                    "action_on_violation": "reject",
                }
            ],
            "priority": random.randint(1, 10),
        }

        with self.client.post(
            "/api/v1/policies",
            json=payload,
            catch_response=True,
            name="POST /policies",
        ) as response:
            if response.status_code in (200, 201, 409):
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")

    @task(6)
    def health_check(self):
        """Health check endpoint (monitoring)."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")


class InfraMindSimulator(HttpUser):
    """
    Simulates InfraMind Decision API submitting action plans.

    Higher frequency, batch operations.
    """

    wait_time = between(10, 30)  # InfraMind polls every 10-30s

    def on_start(self):
        """Called when InfraMind simulator starts."""
        self.client.headers = {
            "Authorization": "Bearer test-system-token",
            "Content-Type": "application/json",
        }

    @task
    def submit_optimization_plan(self):
        """InfraMind submits optimization decisions."""
        plan_id = str(uuid.uuid4())

        # Simulate InfraMind sending multiple decisions at once
        decisions = []
        for _ in range(random.randint(1, 5)):
            decision = {
                "verb": random.choice(["scale", "reschedule", "optimize"]),
                "target": {
                    "namespace": "production",
                    "deployment": f"service-{random.randint(1, 20)}",
                },
                "params": {
                    "replicas": random.randint(2, 10),
                    "reason": "predicted traffic spike",
                },
                "ttl": 600,
                "safety": {"rate_limit": 10, "window": "5m"},
            }
            decisions.append(decision)

        payload = {
            "plan_id": plan_id,
            "source": "inframind",
            "decisions": decisions,
            "created_at": datetime.utcnow().isoformat(),
            "correlation_id": plan_id,
        }

        with self.client.post(
            "/api/v1/action-plans",
            json=payload,
            catch_response=True,
            name="InfraMind: POST /action-plans",
        ) as response:
            if response.status_code in (200, 201, 202):
                response.success()
            elif response.status_code == 429:
                # Rate limited is fine
                response.success()
            else:
                response.failure(f"Got status {response.status_code}")


class CanaryDeploymentUser(HttpUser):
    """
    Simulates canary deployment workflows.

    Tests progressive rollout operations.
    """

    wait_time = between(30, 60)  # Canary updates are less frequent

    def on_start(self):
        """Initialize canary user."""
        self.client.headers = {
            "Authorization": "Bearer test-operator-token",
            "Content-Type": "application/json",
        }

    @task
    def canary_deployment_workflow(self):
        """Complete canary deployment workflow."""
        deployment_id = f"canary-{uuid.uuid4().hex[:8]}"

        # Step 1: Create deployment with canary strategy
        create_payload = {
            "workload_id": "test-workload",
            "cluster_id": "prod-cluster-1",
            "strategy": "canary",
            "replicas": 10,
            "canary": {"steps": [{"percent": 10}, {"percent": 50}, {"percent": 100}]},
        }

        with self.client.post(
            "/api/v1/deployments",
            json=create_payload,
            catch_response=True,
            name="Canary: POST /deployments",
        ) as response:
            if response.status_code not in (200, 201):
                response.failure(f"Create failed: {response.status_code}")
                return

            deployment_id = response.json().get("id", deployment_id)

        # Step 2: Monitor deployment progress
        with self.client.get(
            f"/api/v1/deployments/{deployment_id}",
            catch_response=True,
            name="Canary: GET /deployments/:id",
        ) as response:
            if response.status_code != 200:
                response.failure(f"Monitor failed: {response.status_code}")

        # Step 3: Simulate rollback if needed (10% of the time)
        if random.random() < 0.1:
            with self.client.post(
                f"/api/v1/deployments/{deployment_id}/rollback",
                catch_response=True,
                name="Canary: POST /rollback",
            ) as response:
                if response.status_code in (200, 202):
                    response.success()
                else:
                    response.failure(f"Rollback failed: {response.status_code}")
