"""Configuration management for Failure Ingestion Service."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Service info
    service_name: str = "failure-ingestion"
    version: str = "0.1.0"
    environment: str = "production"

    # Server config
    port: int = 8004
    log_level: str = "INFO"

    # Agent Controller
    agent_controller_url: str = "http://agent-controller:8003"

    # Webhook secrets (for validation)
    github_webhook_secret: Optional[str] = None
    gitlab_webhook_secret: Optional[str] = None

    # Feature flags
    auto_create_tasks: bool = True
    enable_github_webhooks: bool = True
    enable_gitlab_webhooks: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
