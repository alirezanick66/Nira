""" ‫سرویس ثبت غیرهمزمان کوئری‌ها در دیتابیس (Non-Blocking Fire & Forget)"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.models import QueryLog

#────────────────────────────────────────── Configuration ──────────────────────────────────────────
_settings = get_settings()
_engine = create_async_engine( _settings.DATABASE_URL, pool_pre_ping=True )
_session_factory = async_sessionmaker( _engine, class_=AsyncSession, expire_on_commit=False )


#────────────────────────────────────────── Public Methods ──────────────────────────────────────────
def log_query(
    *,
    request_id: uuid.UUID,
    store_id: str,
    session_id: str,
    query: str,
    intent: str,
    latency_ms: int,
    response_status: str,
    domain: str = "mobile",
    user_id: str | None = None,
    client_session_id: str | None = None,
    applied_filters: dict[ str, object ] | None = None,
    result_count: int = 0,
) -> None:
    """ثبت لاگ کوئری به‌صورت Fire & Forget در پس‌زمینه
    
    این تابع بلافاصله بازمی‌گردد و جریان اصلی SSE/HTTP را مسدود نمی‌کند.
    
    Args:
        request_id: شناسهٔ یکتای درخواست
        store_id: شناسهٔ فروشگاه
        session_id: نشست فعال کاربر
        query: متن پرس‌وجوی ورودی
        intent: نیت تشخیص‌داده‌شده
        latency_ms: تأخیر پردازش به میلی‌ثانیه
        response_status: وضعیت پاسخ نهایی
        domain: حوزهٔ درخواستی (پیش‌فرض: mobile)
        user_id: شناسهٔ کاربر (اختیاری)
        client_session_id: نشست سمت کلاینت (اختیاری)
        applied_filters: فیلترهای اعمال‌شده (اختیاری)
        result_count: تعداد نتایج بازگشتی
    """
    entry = QueryLog(
        request_id=request_id,
        store_id=store_id,
        user_id=user_id,
        session_id=session_id,
        client_session_id=client_session_id,
        query=query,
        intent=intent,
        domain=domain,
        applied_filters=applied_filters,
        result_count=result_count,
        response_status=response_status,
        latency_ms=latency_ms,
    )

    # اجرای ایمن Task در پس‌زمینه
    try:
        asyncio.create_task( _write_log( entry ) )
    except RuntimeError:
        # ‫جلوگیری از کرش در صورت بسته بودن Event Loop (هنگام Shutting Down)
        log_message( LG.DATABASE, "لوپ رویداد بسته شد؛ لاگ کوئری ثبت نشد", LogLevel.WARNING )


#────────────────────────────────────────── Private Methods ──────────────────────────────────────────
async def _write_log( entry: QueryLog ) -> None:
    """ثبت ایمن رکورد لاگ ‫با Session مستقل برای جلوگیری از تداخل با Transaction اصلی
    
    Args:
        entry: ‫آبجکت QueryLog آمادهٔ درج
    """
    try:
        async with _session_factory() as session:
            async with session.begin():
                session.add( entry )
    except Exception as exc:
        log_message( LG.DATABASE, f"خطا در ثبت لاگ کوئری (request_id={entry.request_id}): {exc}", LogLevel.ERROR )
