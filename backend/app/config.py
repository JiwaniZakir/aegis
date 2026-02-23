"""ClawdBot — Application configuration via environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    environment: str = "development"
    admin_email: str = ""
    admin_password_hash: str = ""
    jwt_secret: str = Field(min_length=32)
    encryption_master_key: str = Field(min_length=64)

    # --- Database ---
    postgres_user: str = "clawdbot"
    postgres_password: str = Field(min_length=1)
    postgres_db: str = "clawdbot"
    database_url: str = ""
    redis_password: str = Field(min_length=1)
    redis_url: str = ""

    # --- Qdrant ---
    qdrant_api_key: str = ""
    qdrant_url: str = "http://localhost:6333"

    # --- MinIO ---
    minio_root_user: str = "clawdbot"
    minio_root_password: str = ""
    minio_url: str = "http://localhost:9000"

    # --- Plaid ---
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"

    # --- Schwab ---
    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_callback_url: str = ""

    # --- Google ---
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""

    # --- Microsoft ---
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_tenant_id: str = ""

    # --- Canvas ---
    canvas_api_url: str = "https://canvas.drexel.edu/api/v1"
    canvas_access_token: str = ""

    # --- Blackboard ---
    blackboard_url: str = ""
    blackboard_username: str = ""
    blackboard_password: str = ""

    # --- Pearson ---
    pearson_url: str = ""
    pearson_username: str = ""
    pearson_password: str = ""

    # --- LinkedIn ---
    linkedin_email: str = ""
    linkedin_password: str = ""
    linkedin_access_token: str = ""

    # --- X / Twitter ---
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_bearer_token: str = ""

    # --- Anthropic ---
    anthropic_api_key: str = ""

    # --- Deepgram ---
    deepgram_api_key: str = ""

    # --- News ---
    newsapi_key: str = ""

    # --- Cloudflare ---
    cloudflare_tunnel_token: str = ""

    # --- Health ---
    daily_protein_target_g: int = 175
    daily_calorie_limit: int = 1900

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@localhost:5432/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        url = self.async_database_url
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)

    @property
    def redis_connection_url(self) -> str:
        if self.redis_url:
            return self.redis_url
        return f"redis://:{self.redis_password}@localhost:6379/0"

    @property
    def master_key_bytes(self) -> bytes:
        return bytes.fromhex(self.encryption_master_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
