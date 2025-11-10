"""Configuration management for Sentinel Control API."""

from functools import lru_cache
from typing import Any

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Settings
    api_title: str = "Sentinel Control API"
    api_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = False

    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4

    # Database Settings
    database_url: PostgresDsn = Field(
        default="postgresql://sentinel:sentinel@localhost:5432/sentinel"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # JWT Settings
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT token generation",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # CORS Settings
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"]
    )
    cors_allow_credentials: bool = True
    cors_allow_methods: list[str] = Field(default=["*"])
    cors_allow_headers: list[str] = Field(default=["*"])

    # Kafka Settings
    kafka_bootstrap_servers: str = "localhost:9094"
    kafka_topic_events: str = "sentinel.events"
    kafka_topic_deployments: str = "sentinel.deployments"
    kafka_topic_policy_violations: str = "sentinel.policy.violations"

    # Vault Settings
    vault_address: str = "http://localhost:8200"
    vault_token: str = "sentinel-dev-token"
    vault_mount_point: str = "secret"
    vault_path_prefix: str = "sentinel"

    # Prometheus Metrics
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 100

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: Any) -> Any:
        """Validate database URL."""
        if isinstance(v, str):
            return v
        return v

    @property
    def database_url_str(self) -> str:
        """Get database URL as string."""
        if isinstance(self.database_url, str):
            return self.database_url
        return str(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
