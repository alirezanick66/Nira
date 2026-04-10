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

    # ==================== FastApi ====================
    APP_ENV: Literal[ "development", "production" ] = "development"
    APP_DEBUG: bool = True

    # ==================== Scraping ====================
    SCRAPING_BASE_URL: str = "https://www.technolife.com"
    SCRAPING_DELAY_SECONDS: float = 0.3
    SCRAPING_MAX_RETRIES: int = 3


@lru_cache
def get_settings() -> Settings:
    """‫دریافت تنظیمات — Singleton با cache"""
    return Settings()
