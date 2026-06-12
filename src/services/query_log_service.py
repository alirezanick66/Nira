""" ‫سرویس ثبت غیرهمزمان کوئری‌ها در دیتابیس (Non-Blocking Fire & Forget)"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine
#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.models import QueryLog

#────────────────────────────────────────── Configuration ──────────────────────────────────────────
_log_queue: asyncio.Queue[ QueryLog ] = asyncio.Queue( maxsize=1000 )
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[ AsyncSession ] | None = None
_worker_task: asyncio.Task | None = None


#────────────────────────────────────────── Public Methods ──────────────────────────────────────────
def log_query(
    *,
    request_id: uuid.UUID,
    store_id: str,
    session_id: str,
    query: str,
    intent: str,
    latency_ms: float,
    llm_explanation: str | None = None,
    response_status: str,
    domain: str = "mobile",
    user_id: str | None = None,
    client_session_id: str | None = None,
    applied_filters: dict[ str, object ] | None = None,
    result_count: int = 0,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    model_used: str = "unknown",
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
        llm_explanation: پاسخ مدل زبانی (اختیاری)
        domain: حوزهٔ درخواستی (پیش‌فرض: mobile)
        user_id: شناسهٔ کاربر (اختیاری)
        client_session_id: نشست سمت کلاینت (اختیاری)
        applied_filters: فیلترهای اعمال‌شده (اختیاری)
        result_count: تعداد نتایج بازگشتی
        prompt_tokens: تعداد توکن‌های پرامپت
        completion_tokens: تعداد توکن‌های پاسخ
        total_tokens: تعداد کل توکن‌ها
        model_used: مدل استفاده‌شده در پاسخ‌دهی
    """
    _init_log_infrastructure()
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
        llm_explanation=llm_explanation,
          #tokens
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
          #AI model
        model_used=model_used,
    )

    try:
        _log_queue.put_nowait( entry )
    except asyncio.QueueFull:
        log_message( LG.DATABASE, "صف لاگ پر شد (Backpressure). رکورد نادیده گرفته شد.", LogLevel.WARNING )


async def close_log_service() -> None:
    """‫تخلیهٔ صف، بستن Worker و آزادسازی Engine (فراخوانی در Lifespan)"""
    global _worker_task, _engine
    if _worker_task:
        await _log_queue.join()
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    if _engine:
        await _engine.dispose()
        _engine = None


#────────────────────────────────────────── Private Methods ──────────────────────────────────────────


def _init_log_infrastructure() -> None:
    """‫راه‌اندازی ایمن Engine و Worker با بررسی لوپ فعال"""
    global _engine, _session_factory, _worker_task
    if _engine is not None: return
    try:
        asyncio.get_running_loop()          # ✅ بررسی وجود لوپ فعال قبل از ساخت تسک
        settings = get_settings()
        _engine = create_async_engine( settings.DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10 )
        _session_factory = async_sessionmaker( _engine, class_=AsyncSession, expire_on_commit=False )
        _worker_task = asyncio.create_task( _log_worker(), name="query_log_worker" )
    except RuntimeError:
        log_message( LG.DATABASE, "لوپ رویداد فعال نیست؛ زیرساخت لاگ راه‌اندازی نشد.", LogLevel.WARNING )


async def _log_worker() -> None:
    """‫مصرف‌کنندهٔ صف با سِشن ایزوله برای جلوگیری از Memory Leak و Corruption"""
    if _session_factory is None: return
    while True:
        entry = await _log_queue.get()
        try:
            # ‫✅ سِشن داخل حلقه: تخلیه خودکار Identity Map + ایزوله‌سازی خطاها
            async with _session_factory() as session:
                async with session.begin():
                    session.add( entry )
        except Exception as exc:
            log_message( LG.DATABASE, f"خطا در ثبت لاگ (request_id={entry.request_id}): {exc}", LogLevel.ERROR )
        finally:
            _log_queue.task_done()          # ✅‫ در finally قرار داره تا صف گره نخوره
