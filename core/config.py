from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # API Authentication
    api_key: str = "dev-api-key-change-me"

    # Rate Limiting
    rate_limit: int = 100  # requests per minute

    # Optional: OpenAI for custom data extraction
    openai_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # App Info
    app_name: str = "API Toolkit"
    app_version: str = "1.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
