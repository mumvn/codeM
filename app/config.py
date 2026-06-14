from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Microsoft AI Architecture Digest"
    database_path: Path = BASE_DIR / "architecture_digest.db"
    llm_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    request_timeout_seconds: float = 30.0
    max_article_chars: int = 20_000

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
