"""‫مدل‌های SQLAlchemy برای جداول  دیتابیس
‫این ماژول فقط ساختار جداول و ایندکس‌ها را تعریف می‌کند
"""
#────────────────────────────────────────── imports ──────────────────────────────────────────
from __future__ import annotations
from sqlalchemy import Integer, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column, Mapped
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Index, Integer, String, Text, TIMESTAMP
import uuid
from datetime import datetime


class Base( DeclarativeBase ):
    """‫کلاس پایه برای تمامی مدل‌های SQLAlchemy"""
    pass


class ProductRawCache( Base ):
    """جدول کش داده‌های خام API دیجی‌کالا.

    Attributes:
        product_id: شناسهٔ یکتای محصول در فروشگاه (کلید اصلی).
        raw_payload: ‫داده‌های خام JSON دریافتی از API.
        updated_at: زمان آخرین به‌روزرسانی رکورد.
    """
    __tablename__ = "product_raw_cache"

    product_id: Mapped[ int ] = mapped_column( primary_key=True, autoincrement=False )
    raw_payload: Mapped[ dict[ str, object ] ] = mapped_column( JSONB, nullable=False )
    updated_at: Mapped[ datetime ] = mapped_column( DateTime( timezone=True ), server_default=func.now(), onupdate=func.now() )


class SyncProgress( Base ):
    """جدول رهگیری وضعیت همگام‌سازی (الگوی Singleton با id=1).

    Attributes:
        id: شناسهٔ ثابت رکورد پیشرفت (همیشه ۱).
        last_processed_id: آخرین شناسهٔ محصول پردازش‌شده.
        last_page: آخرین صفحهٔ پیمایش‌شده.
        updated_at: زمان آخرین به‌روزرسانی چک‌پوینت.
    """
    __tablename__ = "sync_progress"

    id: Mapped[ int ] = mapped_column( Integer, primary_key=True, default=1 )
    last_processed_id: Mapped[ int | None ] = mapped_column( Integer, nullable=True )
    last_page: Mapped[ int ] = mapped_column( Integer, nullable=False, default=1 )
    updated_at: Mapped[ datetime ] = mapped_column( DateTime( timezone=True ), server_default=func.now(), onupdate=func.now() )


class QueryLog( Base ):
    """جدول لاگ کوئری‌های ورودی از فروشگاه‌ها.

    Attributes:
        id: شناسهٔ یکتای لاگ (تولید خودکار).
        request_id: شناسهٔ درخواست مرتبط.
        store_id: شناسهٔ فروشگاه ارسال‌کننده.
        user_id: شناسهٔ کاربر (اختیاری).
        session_id: شناسهٔ نشست فعال.
        client_session_id: شناسهٔ نشست سمت کلاینت.
        query: متن کوئری ورودی.
        intent: نیت تشخیص‌داده‌شده.
        domain: دسته‌بندی محصول.
        applied_filters: ‫فیلترهای اعمال‌شده در Qdrant.
        result_count: تعداد نتایج بازگشتی.
        response_status: ‫وضعیت پاسخ (success/partial/empty/error).
        latency_ms: تأخیر پردازش به میلی‌ثانیه.
        llm_explanation: پاسخ مدل زبانی   .
        created_at: زمان ثبت رکورد.
    """
    __tablename__ = "query_logs"

    id: Mapped[ uuid.UUID ] = mapped_column( UUID( as_uuid=True ), primary_key=True, default=uuid.uuid4 )
    request_id: Mapped[ uuid.UUID ] = mapped_column( UUID( as_uuid=True ), nullable=False )
    store_id: Mapped[ str ] = mapped_column( String( 50 ), nullable=False )
    user_id: Mapped[ str | None ] = mapped_column( String( 100 ), nullable=True )
    session_id: Mapped[ str ] = mapped_column( String( 100 ), nullable=False )
    client_session_id: Mapped[ str | None ] = mapped_column( String( 100 ), nullable=True )
    query: Mapped[ str ] = mapped_column( Text, nullable=False )
    intent: Mapped[ str ] = mapped_column( String( 20 ), nullable=False )
    domain: Mapped[ str ] = mapped_column( String( 30 ), nullable=False, default="mobile" )
    applied_filters: Mapped[ dict[ str, object ] | None ] = mapped_column( JSONB, nullable=True )
    result_count: Mapped[ int ] = mapped_column( Integer, nullable=False, default=0 )
    response_status: Mapped[ str ] = mapped_column( String( 20 ), nullable=False )
    latency_ms: Mapped[ int ] = mapped_column( Integer, nullable=False )
    llm_explanation: Mapped[ str | None ] = mapped_column( Text, nullable=True, default=None )
    #Token Usage
    prompt_tokens: Mapped[ int | None ] = mapped_column( Integer, nullable=True, default=0 )
    completion_tokens: Mapped[ int | None ] = mapped_column( Integer, nullable=True, default=0 )
    total_tokens: Mapped[ int | None ] = mapped_column( Integer, nullable=True, default=0 )
    model_used: Mapped[ str ] = mapped_column( String, nullable=False, default="groq" )

    created_at: Mapped[ datetime ] = mapped_column( TIMESTAMP( timezone=True ), server_default=func.now(), nullable=False )

    __table_args__ = (
        Index( "idx_query_logs_store_time", "store_id", created_at.desc() ),
        Index( "idx_query_logs_user", "user_id" ),
        Index( "idx_query_logs_intent", "intent" ),
    )
