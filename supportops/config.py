from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Toggle that lets the whole stack run without any external API keys.
    # When true, Claude and OpenAI calls are replaced with deterministic local stubs.
    mock_mode: bool = True

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"

    database_url: str = "postgresql+asyncpg://supportops:supportops@localhost:5432/supportops"

    zendesk_subdomain: str = ""
    zendesk_email: str = ""
    zendesk_api_token: str = ""

    monday_api_token: str = ""
    monday_board_id: str = ""

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    webhook_bridge_port: int = 8787
    python_backend_url: str = "http://localhost:8000"

    # When mock_mode is true we also skip DB calls so unit tests run without Postgres.
    use_inmemory_store: bool = Field(default=False)


@lru_cache
def get_settings() -> Settings:
    return Settings()
