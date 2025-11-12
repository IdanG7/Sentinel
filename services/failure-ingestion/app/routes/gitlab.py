"""GitLab webhook handlers."""

import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from ..config import get_settings
from ..services.agent_client import submit_fix_task
from ..services.parser import GitLabParser

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(tags=["gitlab"])


def verify_gitlab_token(token_header: str) -> bool:
    """
    Verify GitLab webhook token.

    Args:
        token_header: X-Gitlab-Token header value

    Returns:
        True if token is valid
    """
    if not settings.gitlab_webhook_secret:
        logger.warning("GitLab webhook secret not configured, skipping validation")
        return True

    return token_header == settings.gitlab_webhook_secret


@router.post("/pipeline")
async def gitlab_pipeline(
    request: Request,
    x_gitlab_token: str = Header(None),
    x_gitlab_event: str = Header(None),
):
    """
    Handle GitLab pipeline events.

    This endpoint receives notifications when GitLab CI pipelines complete.
    """
    # Verify token
    if not verify_gitlab_token(x_gitlab_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Parse payload
    payload = await request.json()

    # Log event
    logger.info(f"Received GitLab event: {x_gitlab_event}")

    # Parse object kind
    object_kind = payload.get("object_kind")

    if object_kind != "pipeline":
        return {"status": "ignored", "reason": f"object_kind is '{object_kind}', not 'pipeline'"}

    # Get pipeline status
    object_attributes = payload.get("object_attributes", {})
    status_value = object_attributes.get("status")

    # Only process failures
    if status_value != "failed":
        return {"status": "ignored", "reason": f"status is '{status_value}', not 'failed'"}

    # Parse failure details
    try:
        parser = GitLabParser()
        failure_context = await parser.parse_pipeline(payload)

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
        logger.error(f"Failed to process GitLab webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process webhook: {str(e)}",
        )


@router.post("/job")
async def gitlab_job(
    request: Request,
    x_gitlab_token: str = Header(None),
    x_gitlab_event: str = Header(None),
):
    """
    Handle GitLab job events.

    This provides more granular job-level information.
    """
    # Verify token
    if not verify_gitlab_token(x_gitlab_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Parse payload
    payload = await request.json()

    # Log event
    logger.info(f"Received GitLab job event: {x_gitlab_event}")

    # Only process completed jobs
    build_status = payload.get("build_status")

    if build_status != "failed":
        return {"status": "ignored", "reason": f"build_status is '{build_status}', not 'failed'"}

    return {"status": "received", "job_name": payload.get("build_name")}


@router.get("/health")
async def gitlab_health():
    """Health check for GitLab webhooks."""
    return {
        "status": "healthy",
        "enabled": settings.enable_gitlab_webhooks,
    }
