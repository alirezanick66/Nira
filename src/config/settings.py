from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings( BaseSettings ):
    """‫تنظیمات اصلی پروژه"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    #───────────────────── API ─────────────────────
    DIGIKALA_BASE_URL: str = "https://api.digikala.com"
    REQUEST_TIMEOUT: int = 30
    REQUEST_DELAY_SECONDS: float = 0.5
    MAX_RETRIES: int = 3

    #───────────────────── Database ─────────────────────
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "nira_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    POSTGRES_ECHO: bool = False

    DATABASE_URL: str = Field( default=f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}" )

    sync_concurrency: int = Field( default=3, ge=1, le=10, description="حداکثر درخواست همزمان برای استخراج" )

    # ───────────────────── FastApi ─────────────────────
    APP_ENV: Literal[ "development", "production" ] = "development"
    APP_DEBUG: bool = True


@lru_cache
def get_settings() -> Settings:
    """‫دریافت تنظیمات — Singleton با cache"""
    return Settings()
