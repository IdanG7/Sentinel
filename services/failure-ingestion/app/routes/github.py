"""GitHub webhook handlers."""

import hashlib
import hmac
import logging
from typing import Any, Dict

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..config import get_settings
from ..services.agent_client import submit_fix_task
from ..services.parser import GitHubParser

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["github"])


def verify_github_signature(payload_body: bytes, signature_header: str) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload_body: Raw request body
        signature_header: X-Hub-Signature-256 header value

    Returns:
        True if signature is valid
    """
    if not settings.github_webhook_secret:
        logger.warning("GitHub webhook secret not configured, skipping validation")
        return True

    if not signature_header:
        return False

    hash_algorithm, github_signature = signature_header.split("=")

    if hash_algorithm != "sha256":
        return False

    mac = hmac.new(
        settings.github_webhook_secret.encode(),
        msg=payload_body,
        digestmod=hashlib.sha256,
    )

    return hmac.compare_digest(mac.hexdigest(), github_signature)


@router.post("/workflow_run")
async def github_workflow_run(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    """
    Handle GitHub Actions workflow_run events.

    This endpoint receives notifications when GitHub Actions workflows complete.
    """
    # Read raw body
    body = await request.body()

    # Verify signature
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse payload
    payload = await request.json()

    # Log event
    logger.info(f"Received GitHub event: {x_github_event}")

    # Only process completed workflows
    if payload.get("action") != "completed":
        return {"status": "ignored", "reason": "action is not 'completed'"}

    workflow_run = payload.get("workflow_run", {})
    conclusion = workflow_run.get("conclusion")

    # Only process failures
    if conclusion != "failure":
        return {"status": "ignored", "reason": f"conclusion is '{conclusion}', not 'failure'"}

    # Parse failure details
    try:
        parser = GitHubParser()
        failure_context = await parser.parse_workflow_run(payload)

        # Create agent task
        if settings.auto_create_tasks:
            task_id = await submit_fix_task("patchbot", "ci_failure_fix", failure_context)

            logger.info(f"✓ Created fix task {task_id} for {failure_context['repository']}")

            return {
                "status": "task_created",
                "task_id": task_id,
                "repository": failure_context["repository"],
                "failure_type": failure_context.get("failure_type", "unknown"),
            }
        else:
            return {
                "status": "parsed",
                "failure_context": failure_context,
            }

    except Exception as e:
        logger.error(f"Failed to process GitHub webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}",
        )


@router.post("/workflow_job")
async def github_workflow_job(
    request: Request,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    """
    Handle GitHub Actions workflow_job events.

    This provides more granular job-level information.
    """
    # Read raw body
    body = await request.body()

    # Verify signature
    if not verify_github_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    # Parse payload
    payload = await request.json()

    # Log event
    logger.info(f"Received GitHub job event: {x_github_event}")

    # Only process completed jobs
    if payload.get("action") != "completed":
        return {"status": "ignored", "reason": "action is not 'completed'"}

    workflow_job = payload.get("workflow_job", {})
    conclusion = workflow_job.get("conclusion")

    # Only process failures
    if conclusion != "failure":
        return {"status": "ignored", "reason": f"conclusion is '{conclusion}', not 'failure'"}

    return {"status": "received", "job_name": workflow_job.get("name")}


@router.get("/health")
async def github_health():
    """Health check for GitHub webhooks."""
    return {
        "status": "healthy",
        "enabled": settings.enable_github_webhooks,
    }
