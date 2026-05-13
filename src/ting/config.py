from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "dev"
    base_url: str = "http://localhost:8000"
    database_url: str
    valkey_url: str
    session_secret: str = Field(min_length=32)
    goatcounter_site_code: str | None = None
    max_comments_per_code: int = 5
    rate_limit_redemption_per_hour: int = 10
    rate_limit_writes_per_5min: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
