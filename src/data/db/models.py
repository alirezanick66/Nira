"""‫مدل‌های SQLAlchemy برای جداول فیزیکی دیتابیس
‫این ماژول فقط ساختار جداول و ایندکس‌ها را تعریف می‌کند
"""
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy import Index, Integer, String, Text, TIMESTAMP
from datetime import datetime


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


class QueryLog( Base ):
    """جدول لاگ کوئری‌های ورودی از فروشگاه‌ها."""

    __tablename__ = "query_logs"

    id: Mapped[ uuid.UUID ] = mapped_column( UUID( as_uuid=True ), primary_key=True, default=uuid.uuid4 )
    request_id: Mapped[ uuid.UUID ] = mapped_column( UUID( as_uuid=True ), nullable=False )
    store_id: Mapped[ str ] = mapped_column( String( 50 ), nullable=False )
    user_id: Mapped[ str | None ] = mapped_column( String( 100 ), nullable=True )
    session_id: Mapped[ str ] = mapped_column( String( 100 ), nullable=False )
    client_session_id: Mapped[ str | None ] = mapped_column( String( 100 ), nullable=True )
    query: Mapped[ str ] = mapped_column( Text(), nullable=False )
    intent: Mapped[ str ] = mapped_column( String( 20 ), nullable=False )
    domain: Mapped[ str ] = mapped_column( String( 30 ), nullable=False, default="mobile" )
    applied_filters: Mapped[ dict | None ] = mapped_column( JSONB(), nullable=True )
    result_count: Mapped[ int ] = mapped_column( Integer(), nullable=False, default=0 )
    response_status: Mapped[ str ] = mapped_column( String( 10 ), nullable=False )
    latency_ms: Mapped[ int ] = mapped_column( Integer(), nullable=False )
    created_at: Mapped[ datetime ] = mapped_column( TIMESTAMP( timezone=True ), server_default=func.now(), nullable=False )

    __table_args__ = (
        Index( "idx_query_logs_store_time", "store_id", created_at.desc() ),
        Index( "idx_query_logs_user", "user_id" ),
        Index( "idx_query_logs_intent", "intent" ),
    )
