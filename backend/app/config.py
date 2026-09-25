from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./portal.db"
    redis_url: str = "redis://localhost:6379/0"
    public_url: str = "http://localhost:3000"
    openai_api_key: str | None = None
    openai_extraction_model: str = "gpt-5.6-luna"
    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_version: str = "2025-04-01-preview"
    azure_openai_deployment: str = "gpt-6-luna"
    clerk_secret_key: str | None = None
    clerk_webhook_secret: str | None = None
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    resend_api_key: str | None = None
    resend_webhook_secret: str | None = None
    # Keep requests to the same origin deliberately sparse. Increase this for
    # manual audits of larger source sets or when a site's robots policy asks
    # for a longer crawl delay.
    crawler_delay_seconds: float = 3.0
    crawler_timeout_seconds: float = 30.0
    crawler_max_attempts: int = 3
    crawler_max_content_bytes: int = 25_000_000
    artifact_storage_path: Path = Path("/var/lib/portal/artifacts")


@lru_cache
def settings() -> Settings:
    return Settings()
