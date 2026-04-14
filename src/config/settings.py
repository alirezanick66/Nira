from functools import lru_cache
from typing import Literal

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
    DIGIKALA_BASE_URL = "https://api.digikala.com"
    REQUEST_TIMEOUT: int = 30
    REQUEST_DELAY: float = 0.5
    MAX_RETRIES: int = 3

    # ───────────────────── FastApi ─────────────────────
    APP_ENV: Literal[ "development", "production" ] = "development"
    APP_DEBUG: bool = True


@lru_cache
def get_settings() -> Settings:
    """‫دریافت تنظیمات — Singleton با cache"""
    return Settings()
