"""
سرویس لاگ‌گیری کوئری‌ها
ثبت غیرهمزمان (Non-Blocking) اطلاعات هر درخواست در جدول query_logs.
"""
import asyncio
import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from src.config.settings import get_settings
from src.data.db.models import QueryLog

logger = logging.getLogger( __name__ )

# ═══════════════════════════════════════════════════════════════════
# راه‌اندازی موتور دیتابیس به صورت Global (Singleton)
# این کار باعث می‌شود Connection Pool فقط یک‌بار ساخته شود.
# ═══════════════════════════════════════════════════════════════════
_settings = get_settings()
_engine = create_async_engine( _settings.DATABASE_URL )
_session_factory = async_sessionmaker( _engine, class_=AsyncSession, expire_on_commit=False )


async def _write_log( entry: QueryLog ) -> None:
    """
    رکورد لاگ را در دیتابیس ثبت می‌کند.
    از Session مستقل استفاده می‌کند تا با بسته شدن Session درخواست اصلی، دچار خطا نشود.
    """
    try:
        # ایجاد Session جدید و موقت برای این Task
        async with _session_factory() as session:
            async with session.begin():
                session.add( entry )
    except Exception:
        logger.exception( "خطا در ثبت لاگ کوئری — request_id=%s", entry.request_id )


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
    user_id: Optional[ str ] = None,
    client_session_id: Optional[ str ] = None,
    applied_filters: Optional[ dict ] = None,
    result_count: int = 0,
) -> None:
    """
    لاگ یک درخواست را به‌صورت Non-Blocking در پس‌زمینه ثبت می‌کند.
    این تابع بلافاصله return می‌کند و SSE stream را مسدود نمی‌کند.
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

    # اجرای Task در پس‌زمینه (Fire & Forget)
    asyncio.create_task( _write_log( entry ) )
