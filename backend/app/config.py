"""Aegis — Application configuration via environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Only read .env when it exists AND is readable (local dev). Inside Docker,
# env vars come from the compose ``environment:`` block — no .env present.
_env_path = Path(".env")
_env_file: str | None = ".env" if _env_path.is_file() and os.access(_env_path, os.R_OK) else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---
    environment: str = "development"
    admin_email: str = ""
    admin_password_hash: str = ""
    jwt_secret: str = Field(min_length=32)
    encryption_master_key: str = Field(default="", min_length=0)

    # --- CORS ---
    cors_allowed_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="List of allowed CORS origins",
    )

    # --- Docker secret file paths (optional, override env vars) ---
    encryption_master_key_file: str = ""

    # --- Database ---
    # When DATABASE_URL / REDIS_URL are provided (Docker), individual fields
    # are not required. For local dev they come from .env.
    postgres_user: str = "aegis"
    postgres_password: str = ""
    postgres_db: str = "aegis"
    database_url: str = ""
    redis_password: str = ""
    redis_url: str = ""

    # --- Qdrant ---
    qdrant_api_key: str = ""
    qdrant_url: str = "http://localhost:6333"

    # --- MinIO ---
    minio_root_user: str = "aegis"
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

    # --- WhatsApp ---
    whatsapp_bridge_url: str = "http://whatsapp-bridge:3001"

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
        """Load encryption key from Docker secret file if available, else env var."""
        key_hex = self.encryption_master_key
        if self.encryption_master_key_file:
            secret_path = Path(self.encryption_master_key_file)
            if secret_path.is_file():
                key_hex = secret_path.read_text().strip()
        if not key_hex or len(key_hex) < 64:  # noqa: PLR2004
            msg = (
                "ENCRYPTION_MASTER_KEY must be at least 64 hex chars. "
                "Set via env var or ENCRYPTION_MASTER_KEY_FILE pointing to a Docker secret."
            )
            raise ValueError(msg)
        return bytes.fromhex(key_hex)


@lru_cache
def get_settings() -> Settings:
    return Settings()
