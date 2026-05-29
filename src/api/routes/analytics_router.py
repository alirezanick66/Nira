"""‫روتر آنالیتیکس و گزارش‌دهی B2B (فقط خواندنی)"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator
from datetime import datetime, timedelta, timezone

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.engine import DatabaseEngine
from src.data.db.models import QueryLog

router = APIRouter( prefix="/api/v1/admin", tags=[ "Analytics" ] )


#────────────────────────────────────────── Dependencies ──────────────────────────────────────────
async def _get_async_session( request: Request ) -> AsyncGenerator[ AsyncSession, None ]:
    """‫تزریق سشن دیتابیس از DatabaseEngine موجود در app.state"""
    db_engine: DatabaseEngine = request.app.state.db_engine
    async with db_engine.session_maker() as session:
        yield session


#────────────────────────────────────────── Routes ──────────────────────────────────────────


@router.get( "/stats", summary="آمار تجمیعی داشبورد" )
async def get_dashboard_stats(
        days: int = Query( default=7, ge=1, le=30, description="بازه زمانی به روز (۱، ۷، ۳۰)" ),
        session: AsyncSession = Depends( _get_async_session ),
):
    """‫محاسبه آمار کلی: میانگین تأخیر، مجموع توکن‌ها، تعداد کوئری‌ها و نرخ خطا"""

    try:
        since = _date_filter( days )
        agg_query = ( select(
            func.avg( QueryLog.latency_ms ).label( "avg_latency" ),
            func.sum( QueryLog.total_tokens ).label( "total_tokens" ),
            func.count( QueryLog.id ).label( "total_queries" ),
            func.count( QueryLog.id ).filter( QueryLog.response_status == "error" ).label( "error_count" ),
            func.count( QueryLog.id ).filter( QueryLog.intent == "general_chat" ).label( "greeting_unrelated" ),
            func.count( QueryLog.id ).filter( QueryLog.response_status == "clarification" ).label( "clarification" ),
            func.count( QueryLog.id ).filter( QueryLog.response_status == "empty" ).label( "zero_results" ),
            func.avg( QueryLog.result_count ).label( "avg_result_count" ),
        ).where( QueryLog.created_at >= since ) )
        res = await session.execute( agg_query )
        stats = res.mappings().first()

        if stats is None:
            return _empty_stats()

        total = max( stats[ "total_queries" ] or 0, 1 )
        search_refine = max(
            0,
            total - ( stats[ "greeting_unrelated" ] or 0 ) - ( stats[ "clarification" ] or 0 ) - ( stats[ "error_count" ] or 0 ),
        )

        return {
            "avg_latency_ms": round( stats[ "avg_latency" ] or 0, 1 ),
            "total_tokens": stats[ "total_tokens" ] or 0,
            "total_queries": total,
            "error_rate_pct": f"{((stats['error_count'] or 0) / total) * 100:.1f}",
            "zero_results_count": stats[ "zero_results" ] or 0,
            "zero_results_rate_pct": f"{((stats['zero_results'] or 0) / total) * 100:.1f}",
            "avg_result_count": round( stats[ "avg_result_count" ] or 0, 1 ),
            "intent_breakdown": {
                "greeting_unrelated": stats[ "greeting_unrelated" ] or 0,
                "clarification": stats[ "clarification" ] or 0,
                "search_refine": search_refine,
            },
        }
    except Exception as exc:
        log_message( LG.API, f"خطا در محاسبه آمار داشبورد: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=500, detail="خطا در محاسبه آمار" )


@router.get( "/logs", summary="لیست خام کوئری‌ها با پیجینیشن" )
async def get_query_logs(
        limit: int = 20,
        offset: int = 0,
        days: int = Query( default=7, ge=1, le=30, description="بازه زمانی به روز (۱، ۷، ۳۰)" ),
        session: AsyncSession = Depends( _get_async_session ),
):
    """‫بازیابی لاگ‌های کوئری با پشتیبانی از pagination واقعی (total count)"""
    try:
        since = _date_filter( days )
        # ‫شمارش کل رکوردها برای pagination صحیح در فرانت‌اند
        count_stmt = ( select( func.count( QueryLog.id ) ).where( QueryLog.created_at >= since ) )
        total_result = await session.execute( count_stmt )
        total_count: int = total_result.scalar_one()

        stmt = ( select( QueryLog ).where( QueryLog.created_at >= since ).order_by( desc(
            QueryLog.created_at ) ).limit( limit ).offset( offset ) )
        result = await session.execute( stmt )
        logs = [ log.__dict__ for log in result.scalars().all() ]
        clean_logs = [ { k: v for k, v in l.items() if not k.startswith( "_" ) } for l in logs ]

        return {
            "logs": clean_logs,
            "count": len( clean_logs ),
            "total": total_count,
        }
    except Exception as exc:
        log_message( LG.API, f"خطا در بازیابی لاگ‌های کوئری: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=500, detail="خطا در بازیابی لاگ‌ها" )


#────────────────────────────────────────── Private Helpers ──────────────────────────────────────────


def _empty_stats() -> dict:
    """‫پاسخ پیش‌فرض در صورت خالی بودن جدول"""
    return {
        "avg_latency_ms": 0,
        "total_tokens": 0,
        "total_queries": 0,
        "error_rate_pct": "0.0",
        "zero_results_count": 0,
        "zero_results_rate_pct": "0.0",
        "avg_result_count": 0,
        "intent_breakdown": {
            "greeting_unrelated": 0,
            "clarification": 0,
            "search_refine": 0,
        },
    }


def _date_filter( days: int ) -> datetime:
    """‫محاسبه تاریخ شروع بازه زمانی بر اساس تعداد روز"""
    return datetime.now( timezone.utc ) - timedelta( days=days )
