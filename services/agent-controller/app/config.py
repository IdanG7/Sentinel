"""Configuration for Agent Controller."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Service Settings
    service_name: str = "agent-controller"
    version: str = "0.1.0"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8082

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel",
        description="Database connection URL",
    )

    # Redis (Task Queue)
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for task queue",
    )
    redis_max_connections: int = 50

    # Task Queue Settings
    task_queue_size: int = 1000
    task_default_timeout_seconds: int = 600
    task_retry_attempts: int = 3
    task_retry_delay_seconds: int = 60

    # Sandboxing
    sandbox_enabled: bool = True
    sandbox_timeout_seconds: int = 600
    sandbox_memory_limit_mb: int = 2048
    sandbox_cpu_limit: float = 2.0

    # Rate Limiting
    max_concurrent_tasks: int = 10
    max_tasks_per_agent: int = 5
    rate_limit_per_hour: int = 50
    rate_limit_per_day: int = 200

    # Auto-Remediation Policies
    auto_merge_confidence_threshold: float = 0.9
    auto_create_pr_confidence_threshold: float = 0.7
    require_review_below_confidence: float = 0.7
    max_concurrent_fixes: int = 3
    cooldown_after_failure_minutes: int = 60

    # InfraMind Integration
    inframind_url: str = "http://localhost:50051"
    inframind_enabled: bool = True

    # Prometheus
    metrics_port: int = 9102


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
