"""‫روتر آنالیتیکس و گزارش‌دهی B2B (فقط خواندنی)"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.engine import DatabaseEngine
from src.data.db.models import QueryLog
from typing import AsyncGenerator

router = APIRouter( prefix="/api/v1/admin", tags=[ "Analytics" ] )


async def get_async_session( request: Request ) -> AsyncGenerator[ AsyncSession, None ]:
    db_engine: DatabaseEngine = request.app.state.db_engine
    async with db_engine.session_maker() as session:
        yield session


@router.get( "/stats", summary="آمار تجمیعی داشبورد" )
async def get_dashboard_stats( session: AsyncSession = Depends( get_async_session ) ):
    try:
        agg_query = select(
            func.avg( QueryLog.latency_ms ).label( "avg_latency" ),
            func.sum( QueryLog.total_tokens ).label( "total_tokens" ),
            func.count( QueryLog.id ).label( "total_queries" ),
            func.count( QueryLog.id ).filter( QueryLog.response_status == "error" ).label( "error_count" ),
            func.count( QueryLog.id ).filter( QueryLog.intent == "general_chat" ).label( "greeting_unrelated" ),
            func.count( QueryLog.id ).filter( QueryLog.response_status == "clarification" ).label( "clarification" ),
        )
        res = await session.execute( agg_query )
        stats = res.mappings().first()

        # ‫✅ گارد صریح برای رفع خطای Optional Subscript
        if stats is None:
            return {
                "avg_latency_ms": 0,
                "total_tokens": 0,
                "total_queries": 0,
                "error_rate_pct": "0.0",
                "intent_breakdown": {
                    "greeting_unrelated": 0,
                    "clarification": 0,
                    "search_refine": 0
                }
            }

        total = max( stats[ "total_queries" ] or 0, 1 )

        return {
            "avg_latency_ms": round( stats[ "avg_latency" ] or 0, 1 ),
            "total_tokens": stats[ "total_tokens" ] or 0,
            "total_queries": total,
            "error_rate_pct": f"{((stats['error_count'] or 0) / total) * 100:.1f}",
            "intent_breakdown": {
                "greeting_unrelated":
                stats[ "greeting_unrelated" ] or 0,
                "clarification":
                stats[ "clarification" ] or 0,
                "search_refine":
                max(
                    0, total - ( stats[ "greeting_unrelated" ] or 0 ) - ( stats[ "clarification" ] or 0 ) -
                    ( stats[ "error_count" ] or 0 ) )
            }
        }
    except Exception as e:
        log_message( LG.API, f"خطا در آمار: {e}", LogLevel.ERROR )
        raise HTTPException( status_code=500, detail="خطا در محاسبه آمار" )


@router.get( "/logs", summary="لیست خام کوئری‌ها با پیجینیشن" )
async def get_query_logs( limit: int = 50, offset: int = 0, session: AsyncSession = Depends( get_async_session ) ):
    try:
        stmt = select( QueryLog ).order_by( desc( QueryLog.created_at ) ).limit( limit ).offset( offset )
        result = await session.execute( stmt )
        logs = [ log.__dict__ for log in result.scalars().all() ]
        clean_logs = [ { k: v for k, v in l.items() if not k.startswith( "_" ) } for l in logs ]
        return { "logs": clean_logs, "count": len( clean_logs ) }
    except Exception as e:
        raise HTTPException( status_code=500, detail="خطا در بازیابی لاگ‌ها" )
