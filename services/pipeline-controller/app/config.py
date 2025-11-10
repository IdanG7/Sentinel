"""Configuration management for Pipeline Controller."""

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
    service_name: str = "pipeline-controller"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # Kafka Settings
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_consumer_group: str = "sentinel-pipeline-controller"
    kafka_topic_deployments: str = "sentinel.deployments"
    kafka_topic_action_plans: str = "sentinel.action-plans"
    kafka_topic_events: str = "sentinel.events"

    # Policy Engine Settings
    policy_engine_mode: str = Field(
        default="enforce",
        description="Policy engine mode: enforce, dry_run, audit",
    )

    # Kubernetes Settings
    kubeconfig_path: str = Field(
        default="~/.kube/config",
        description="Path to kubeconfig file",
    )
    default_namespace: str = "default"

    # Reconciliation Settings
    reconciliation_interval_seconds: int = 30
    max_concurrent_deployments: int = 10

    # Health Check Settings
    health_check_interval_seconds: int = 60
    health_check_timeout_seconds: int = 30

    # Rollback Settings
    auto_rollback_enabled: bool = True
    rollback_threshold_failure_percent: int = 50


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
