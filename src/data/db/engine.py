"""‫مدیریت چرخه حیات اتصال به PostgreSQL
‫راه‌اندازی Engine، SessionMaker و اعتبارسنجی اولیهٔ اتصال.
"""
#─────────────────────imports─────────────────────
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

#─────────────────────local imports─────────────────────
from src.config.settings import get_settings
from src.data.db.models import Base
from src.config.logging_config import LG, LogLevel, log_message


class DatabaseEngine:
    """مدیریت‌کنندهٔ اتصال غیرهمزمان به دیتابیس و فکتوری ساخت Sessionها."""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._engine = create_async_engine(
            self._settings.DATABASE_URL,
            echo=self._settings.DB_ECHO,
            pool_size=self._settings.POOL_SIZE,
            max_overflow=self._settings.MAX_OVERFLOW,
            pool_recycle=3600,
            pool_pre_ping=True,          #بررسی خودکار سلامت اتصال قبل از استفاده
        )
        self._session_maker = async_sessionmaker( bind=self._engine, expire_on_commit=False, class_=AsyncSession )
        log_message( LG.DATABASE, "DatabaseEngine با موفقیت پیکربندی شد", LogLevel.INFO )

    async def init_db( self ) -> None:
        """‫ایجاد جداول در صورت عدم وجود (مناسب توسعه)"""
        async with self._engine.begin() as conn:
            await conn.run_sync( Base.metadata.create_all )
        log_message( LG.DATABASE, "جداول دیتابیس بررسی/ایجاد شدند", LogLevel.INFO )

    async def close( self ) -> None:
        """‫بستن تمام کانکشن‌ها و آزادسازی منابع"""
        if self._engine:
            await self._engine.dispose()
            log_message( LG.DATABASE, "اتصالات دیتابیس به‌طور ایمن بسته شدند", LogLevel.INFO )

    @property
    def session_maker( self ) -> async_sessionmaker[ AsyncSession ]:
        """‫فکتوری ساخت Sessionهای غیرهمزمان"""
        return self._session_maker
