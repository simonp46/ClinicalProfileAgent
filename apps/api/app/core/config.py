"""Application configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_env: Literal["development", "test", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_log_level: str = "INFO"
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    web_app_url: str = "http://localhost:3000"

    secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    csrf_enabled: bool = True
    csrf_cookie_name: str = "tmc_csrf"
    refresh_cookie_name: str = "tmc_refresh"

    database_url: str = "postgresql+psycopg://therapy:therapy@localhost:5432/therapy_copilot"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: int = 60
    openai_max_retries: int = 3
    prompt_version: str = "v1"

    google_project_id: str | None = None
    google_workspace_events_audience: str | None = None
    google_webhook_shared_secret: str | None = None
    google_service_account_file: str | None = None
    google_impersonated_user: str | None = None
    google_docs_output_folder_id: str | None = None
    google_transcript_fetch_enabled: bool = False
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None

    microsoft_oauth_client_id: str | None = None
    microsoft_oauth_client_secret: str | None = None
    microsoft_oauth_tenant_id: str = "common"
    microsoft_oauth_redirect_uri: str | None = None
    artifacts_dir: str = "/tmp/therapy-meet-copilot"
    use_mock_openai: bool = True
    use_mock_google: bool = True

    encryption_key: str | None = None

    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "therapy-meet-copilot-api"

    @field_validator("api_cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [part.strip() for part in value.split(",") if part.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

