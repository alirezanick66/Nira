"""‫مدیریت چرخه حیات اتصال به PostgreSQL
‫این ماژول Engine و SessionMaker غیرهمزمان را مدیریت می‌کند.
"""
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config.settings import get_settings
from src.data.db.models import Base


class DatabaseEngine:
    """‫راه‌انداز و مدیریت‌کنندهٔ اتصال غیرهمزمان به دیتابیس"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._engine = create_async_engine(
            self._settings.DATABASE_URL,
            echo=self._settings.POSTGRES_ECHO,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,
        )
        self._session_maker = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    async def init_db( self ) -> None:
        """‫ایجاد جداول در صورت عدم وجود (مناسب توسعه)"""
        async with self._engine.begin() as conn:
            await conn.run_sync( Base.metadata.create_all )

    async def close( self ) -> None:
        """‫بستن تمام کانکشن‌ها و آزادسازی منابع"""
        await self._engine.dispose()

    @property
    def session_maker( self ) -> async_sessionmaker:
        """‫فکتوری ساخت Sessionهای غیرهمزمان"""
        return self._session_maker
