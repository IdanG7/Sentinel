"""PatchBot configuration."""

import os
from typing import Optional

from pydantic import BaseModel, Field


class PatchBotConfig(BaseModel):
    """PatchBot configuration."""

    # Agent Controller
    controller_url: str = Field(
        default_factory=lambda: os.getenv("AGENT_CONTROLLER_URL", "http://localhost:8003")
    )

    # Claude AI
    anthropic_api_key: str = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    claude_model: str = Field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    )
    max_tokens: int = 4096
    temperature: float = 0.7

    # GitHub
    github_token: str = Field(
        default_factory=lambda: os.getenv("GITHUB_TOKEN", "")
    )
    github_org: Optional[str] = Field(
        default_factory=lambda: os.getenv("GITHUB_ORG")
    )

    # Git
    git_author_name: str = Field(
        default_factory=lambda: os.getenv("GIT_AUTHOR_NAME", "PatchBot")
    )
    git_author_email: str = Field(
        default_factory=lambda: os.getenv("GIT_AUTHOR_EMAIL", "patchbot@sentinel.ai")
    )

    # Behavior
    auto_merge_confidence_threshold: float = 0.9
    create_branch: bool = True
    open_pr: bool = True
    pr_labels: list[str] = Field(default_factory=lambda: ["bot", "ci-fix", "automated"])
    max_retries: int = 3

    # Workspace
    workspace_dir: str = Field(
        default_factory=lambda: os.getenv("WORKSPACE_DIR", "/tmp/patchbot-workspace")
    )
    cleanup_workspace: bool = True

    class Config:
        """Pydantic config."""

        env_file = ".env"
        env_file_encoding = "utf-8"


def get_config() -> PatchBotConfig:
    """Get PatchBot configuration."""
    return PatchBotConfig()
