"""‫مدل‌های SQLAlchemy برای جداول فیزیکی دیتابیس
‫این ماژول فقط ساختار جداول و ایندکس‌ها را تعریف می‌کند
"""
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped


class Base( DeclarativeBase ):
    """‫کلاس پایه برای تمامی مدل‌های SQLAlchemy"""
    pass


class ProductRawCache( Base ):
    """‫جدول کش داده‌های خام API دیجی‌کالا
    """
    __tablename__ = "product_raw_cache"

    product_id: Mapped[ int ] = mapped_column( primary_key=True, autoincrement=False, comment="شناسهٔ یکتای محصول در فروشگاه" )
    raw_payload: Mapped[ dict[ str, object ] ] = mapped_column( JSONB, nullable=False, comment="داده‌های خام JSON دریافتی" )
    updated_at: Mapped[ DateTime ] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="زمان آخرین به‌روزرسانی",
    )


class SyncProgress( Base ):
    """جدول رهگیری وضعیت همگام‌سازی (الگوی Singleton با id=1)."""
    __tablename__ = "sync_progress"

    id: Mapped[ Integer ] = mapped_column( Integer, primary_key=True, default=1, comment="شناسهٔ ثابت رکورد پیشرفت" )
    last_processed_id: Mapped[ Integer ] = mapped_column( Integer, nullable=True, comment="آخرین  ایدی  پردازش شده" )
    last_page: Mapped[ Integer ] = mapped_column( Integer, nullable=False, default=1, comment="آخرین صفحهٔ پیمایش شده" )
    updated_at: Mapped[ DateTime ] = mapped_column( DateTime,
                                                    server_default=func.now(),
                                                    onupdate=func.now(),
                                                    comment="زمان آخرین به‌روزرسانی" )
