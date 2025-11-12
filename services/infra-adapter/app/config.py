"""Configuration for InfraMind Adapter."""

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
    service_name: str = "infra-adapter"
    version: str = "0.1.0"
    log_level: str = "INFO"

    # InfraMind Settings
    inframind_url: str = Field(
        default="localhost:50051",
        description="InfraMind gRPC server address",
    )
    inframind_tls_enabled: bool = False
    inframind_tls_cert_path: str = ""

    # Prometheus Settings
    prometheus_url: str = "http://localhost:9090"
    telemetry_batch_interval_seconds: int = 60
    telemetry_query_range_seconds: int = 300

    # Kafka Settings
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_consumer_group: str = "sentinel-infra-adapter"
    kafka_topic_events: str = "sentinel.events"
    kafka_topic_deployments: str = "sentinel.deployments"

    # Control API Settings
    control_api_url: str = "http://localhost:8000/api/v1"
    control_api_token: str = ""

    # Batching Settings
    max_batch_size: int = 1000
    max_batch_age_seconds: int = 30

    # InfraMind REST API Settings (for decision brain)
    inframind_api_url: str = "http://localhost:8081"
    inframind_api_key: str = ""
    inframind_api_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
