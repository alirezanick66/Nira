#────────────────────────────────────────── Imports ──────────────────────────────────────────
from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic.fields import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings( BaseSettings ):
    """‫تنظیمات اصلی پروژه"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    #────────────────────────────────────────── API ──────────────────────────────────────────
    DIGIKALA_BASE_URL: str = "https://api.digikala.com"
    REQUEST_TIMEOUT: int = 30
    REQUEST_DELAY_SECONDS: float = 0.5
    REQUEST_DELAY_RANGE: float = 0.5
    MAX_RETRIES: int = 3

    #────────────────────────────────────────── Database ──────────────────────────────────────────
    DB_USER: str = Field( default="postgres" )
    DB_PASSWORD: str = Field( default="postgres" )
    DB_HOST: str = Field( default="localhost" )
    DB_PORT: int = Field( default=5432 )
    DB_NAME: str = Field( default="nira_db" )
    DB_ECHO: bool = False
    POOL_SIZE: int = Field( default=5 )
    MAX_OVERFLOW: int = Field( default=10 )

    sync_concurrency: int = Field( default=3, ge=1, le=10, description="حداکثر درخواست همزمان برای استخراج" )

    # ────────────────────────────────────────── FastApi ──────────────────────────────────────────
    APP_NAME: str = "Nira"
    APP_DEBUG: bool = True

    # ──────────────────────────────────────────  Qdrant Vector DB ──────────────────────────────────────────
    QDRANT_URL: str = Field( default="http://localhost:6333" )
    QDRANT_COLLECTION: str = Field( default="nira_products" )
    EMBEDDING_MODEL_PATH: Path = Field( default=Path( "" ), description="مسیر محلی مدل Embedding" )
    EMBEDDING_DIM: int = Field( default=768, description="ابعاد بردارهای Embedding" )

    #────────────────────────────────────────── Reranker ──────────────────────────────────────────
    RERANKER_MODEL_PATH: Path = Field( default=Path( "" ), description="مسیر محلی مدل Reranker" )
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"
    RERANKER_BATCH_SIZE: int = 8
    # ‫MVP Refinement: آستانه فیلتر نتایج کم‌ربط بعد اضافه شدن دیتا های ساختاریافته محاسبه میشود
    RERANKER_MIN_SCORE: float = Field( default=0.02, ge=0.0, le=1.0, description="حداقل امتیاز Sigmoid برای پذیرش یک نتیجه در Top-k" )
    RERANKER_TOP_K: int = Field( default=3, ge=1, le=20, description="تعداد محصولات Top-k نهایی پس از Reranking" )

    #────────────────────────────────────────── LLM ──────────────────────────────────────────
    #Api Keys
    GROQ_API_KEY: str = Field( default="", description=" ‫کلید API برای دسترسی به سرویس Groq" )
    GEMINI_API_KEY: str = Field( default="", description=" ‫کلید API برای دسترسی به سرویس Gemini" )
    #Model Names
    GROQ_MODEL: str = Field( default="llama-3.3-70b-versatile", description=" ‫مدل Groq برای تولید پاسخ" )
    GEMINI_MODEL: str = Field( default="gemini-2.5-flash", description=" ‫مدل Gemini برای تولید پاسخ " )

    # ────────────────────────────────────────── ONNX Runtime ──────────────────────────────────────────
    USE_ONNX: bool = Field( default=True, description="فعال‌سازی ONNX Runtime برای کاهش مصرف CPU/RAM" )
    ONNX_EMBEDDING_PATH: Path = Field( default=Path( "" ), description="‫مسیر مدل Embedding کوانتایز شده (INT8)" )
    ONNX_RERANKER_PATH: Path = Field( default=Path( "" ), description="‫مسیر مدل Reranker کوانتایز شده (INT8)" )

    #────────────────────────────────────────── API Key Store ──────────────────────────────────────────
    API_KEY_STORE_MAP: str = Field( default="" )

    # ────────────────────────────────────────── Computed Fields ──────────────────────────────────────────
    @computed_field
    @property
    def DATABASE_URL( self ) -> str:
        """‫‫ساخت آدرس اتصال PostgreSQL  """
        return ( f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}"
                 f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}" )

    @computed_field
    @property
    def SYNC_DB_URL( self ) -> str:
        """‫آدرس اتصال برای Alembic (همان DATABASE_URL)"""
        return self.DATABASE_URL


@lru_cache()
def get_settings() -> Settings:
    """‫دریافت تنظیمات — Singleton با cache"""
    return Settings()
