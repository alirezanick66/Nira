"""‫مدل‌های SQLAlchemy برای جداول فیزیکی دیتابیس
‫این ماژول فقط ساختار جداول و ایندکس‌ها را تعریف می‌کند.
"""
from sqlalchemy import Column, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base( DeclarativeBase ):
    """‫کلاس پایه برای تمامی مدل‌های SQLAlchemy"""
    pass


class ProductRawCache( Base ):
    """‫جدول کش داده‌های خام API دیجی‌کالا
    ‫فقط شامل شناسه محصول، payload خام JSONB و زمان آخرین به‌روزرسانی
    """
    __tablename__ = "product_raw_cache"

    product_id = Column( Integer, primary_key=True, autoincrement=False )
    raw_payload = Column( JSONB, nullable=False )
    updated_at = Column( DateTime, nullable=False, server_default=func.now(), onupdate=func.now() )


class SyncProgress( Base ):
    """‫جدول وضعیت همگام‌سازی (Singleton با id=1)"""
    __tablename__ = "sync_progress"

    id = Column( Integer, primary_key=True, default=1 )
    last_processed_id = Column( Integer, nullable=True )
    last_page = Column( Integer, nullable=False, default=1 )
    updated_at = Column( DateTime, server_default=func.now(), onupdate=func.now() )
