import os
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseAppSettings(BaseSettings):
    """
    Base configuration for Oponn.
    Loads from .env and .env.{OPONN_ENV} files.
    """

    # We determine the env file names dynamically before class initialization
    _env = os.getenv("OPONN_ENV", "development").lower()
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_env}"), env_file_encoding="utf-8", extra="ignore"
    )

    # Core Environment
    oponn_env: Literal["development", "testing", "staging", "production"] = (
        "development"
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["pretty", "json"] = "pretty"
    secret_key: str = "dev_secret_key_change_in_prod"

    # Infrastructure (Defaults to None for Zero-Config Dev/Test)
    database_url: PostgresDsn | None = None
    redis_url: RedisDsn | None = None

    @field_validator("database_url", "redis_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        if v == "":
            return None
        return v

    # Security / CSRF
    oponn_skip_csrf: bool = False

    # OAuth
    use_mock_auth: bool = True
    google_client_id: str = "mock-id"
    google_client_secret: str = "mock-secret"
    github_client_id: str = "mock-id"
    github_client_secret: str = "mock-secret"

    # AWS / KMS
    oponn_kms_key_id: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    localstack_endpoint: str | None = "http://localhost:4566"

    @property
    def is_production(self) -> bool:
        return self.oponn_env == "production"

    @property
    def is_staging(self) -> bool:
        return self.oponn_env == "staging"

    @property
    def is_testing(self) -> bool:
        return self.oponn_env == "testing"

    @property
    def is_in_memory(self) -> bool:
        """Returns True if the application should use in-memory repositories."""
        return self.database_url is None


class DevelopmentSettings(BaseAppSettings):
    """Configuration for development environment."""

    oponn_env: Literal["development"] = "development"  # type: ignore
    log_format: Literal["pretty"] = "pretty"  # type: ignore


class TestingSettings(BaseAppSettings):
    """Configuration for testing environment."""

    oponn_env: Literal["testing"] = "testing"  # type: ignore
    oponn_skip_csrf: bool = True
    log_format: Literal["pretty"] = "pretty"  # type: ignore


class StagingSettings(BaseAppSettings):
    """Configuration for staging environment. Mirrors production requirements."""

    oponn_env: Literal["staging"] = "staging"  # type: ignore
    log_format: Literal["pretty"] = "pretty"  # type: ignore
    use_mock_auth: bool = True

    # Enforce required infrastructure
    database_url: PostgresDsn  # type: ignore
    redis_url: RedisDsn  # type: ignore
    oponn_kms_key_id: str  # type: ignore

    @field_validator("oponn_skip_csrf")
    @classmethod
    def no_skip_csrf_in_staging(cls, v: bool) -> bool:
        if v:
            raise ValueError("OPONN_SKIP_CSRF cannot be true in staging mode")
        return False


class ProductionSettings(BaseAppSettings):
    """Configuration for production environment. Enforces strict requirements."""

    oponn_env: Literal["production"] = "production"  # type: ignore
    log_format: Literal["json"] = "json"  # type: ignore
    use_mock_auth: bool = False

    # Enforce required infrastructure
    database_url: PostgresDsn  # type: ignore
    redis_url: RedisDsn  # type: ignore
    oponn_kms_key_id: str  # type: ignore

    @field_validator("localstack_endpoint")
    @classmethod
    def no_localstack_in_prod(cls, v: str | None) -> str | None:
        if v:
            raise ValueError("LOCALSTACK_ENDPOINT cannot be set in production mode")
        return None

    @field_validator("oponn_skip_csrf")
    @classmethod
    def no_skip_csrf_in_prod(cls, v: bool) -> bool:
        if v:
            raise ValueError("OPONN_SKIP_CSRF cannot be true in production mode")
        return False


def get_settings() -> BaseAppSettings:
    """Factory to return the correct settings object based on OPONN_ENV."""
    env = os.getenv("OPONN_ENV", "development").lower()

    if env == "production":
        return ProductionSettings()
    elif env == "staging":
        return StagingSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()


settings = get_settings()
