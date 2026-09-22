from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./portal.db"
    redis_url: str = "redis://localhost:6379/0"
    public_url: str = "http://localhost:3000"
    openai_api_key: str | None = None
    openai_extraction_model: str = "gpt-5.6-luna"
    clerk_secret_key: str | None = None
    clerk_webhook_secret: str | None = None
    clerk_jwks_url: str | None = None
    clerk_issuer: str | None = None
    resend_api_key: str | None = None
    resend_webhook_secret: str | None = None


@lru_cache
def settings() -> Settings:
    return Settings()
