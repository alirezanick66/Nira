"""‫روتر اختصاصی جستجوی محصولات

‫این ماژول فقط مسئول:
‫۱. دریافت درخواست HTTP (POST یا GET/SSE)
‫۲. تفویض کامل منطق به SearchService
‫۳. لاگ‌گیری هر درخواست (cross-cutting concern)
‫است و هیچ منطق تجاری مستقیمی ندارد.
"""

#──────────────────────────────────────────  Imports ──────────────────────────────────────────
from __future__ import annotations
import json
import time
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.data.repositories.product_repository import ProductRepository
from src.api.schemas import SearchRequest
from src.core.schemas import SearchResponse
from src.services.search_service import PipelineStatus, SearchService
from src.api.dependencies import get_retriever, get_reranker, get_llm, get_product_repo, get_search_service
from src.services.query_log_service import log_query
from src.core.llm.orchestrator import LLMOrchestrator
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.config.logging_config import log_message, LogLevel, LG

router = APIRouter( prefix="/api/v1", tags=[ "Search" ] )

# ──────────────────────────────────────────  فرمت‌بندی رویداد SSE──────────────────────────────────────────


def _sse_event( event: str, data: dict ) -> str:
    """‫فرمت‌بندی یک رویداد SSE استاندارد"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ────────────────────────────────────────── Endpoint 1: جستجوی B2B ──────────────────────────────────────────


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="جستجوی محصول — قرارداد رسمی B2B",
    response_description="پاسخ کامل JSON پس از اجرای کامل پایپلاین",
)
async def search_products(
    request_body: SearchRequest,
    request: Request,
    service: SearchService = Depends( get_search_service ),
    retriever: QdrantHybridRetriever = Depends( get_retriever ),
    reranker: RerankerService = Depends( get_reranker ),
    llm: LLMOrchestrator = Depends( get_llm ),
    product_repo: ProductRepository = Depends( get_product_repo )
) -> SearchResponse:
    """‫دریافت کوئری از فروشگاه، اجرای کامل پایپلاین و بازگشت JSON ساختاریافته.

    ‫این endpoint پایدار، کش‌پذیر و فاقد وابستگی به پروتکل SSE است.
    ‫session_id بازگشتی را در درخواست بعدی برای فعال‌سازی حافظه مکالمه ارسال کنید.
    """
    t0 = time.perf_counter()
    store_id: str = request.state.store_id
    session_id: str = request_body.client_session_id or str( uuid.uuid4() )
    response_status = "error"
    result_intent = "unknown"

    response: SearchResponse | None = None
    try:
        response, _ = await service.run(
            query=request_body.query,
            session_id=session_id,
            top_k=request_body.top_k,
        )
        response_status = response.status
        result_intent = response.intent
        return response

    except HTTPException:
        raise
    except Exception:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در POST /search | Query: {request_body.query[:50]}", LogLevel.ERROR )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطای داخلی سرور.",
        )
    finally:
        tokens = response.meta.get( "token_usage", {} ) if response and response.meta else {}
        model_used = str( response.meta.get( "model_used", "unknown" ) ) if response and response.meta else "error"

        log_query(
            request_id=uuid.uuid4(),
            store_id=store_id,
            user_id=request_body.user_id,
            session_id=session_id,
            client_session_id=request_body.client_session_id,
            query=request_body.query,
            intent=result_intent,
            domain=request_body.domain or "mobile",
            applied_filters=response.applied_filters if response else None,
            result_count=len( response.results ) if response else 0,
            response_status=response_status,
            latency_ms=int( ( time.perf_counter() - t0 ) * 1000 ),
          #tokens
            prompt_tokens=tokens.get( "prompt_tokens", 0 ),          #type:ignore
            completion_tokens=tokens.get( "completion_tokens", 0 ),          #type:ignore
            total_tokens=tokens.get( "total_tokens", 0 ),          #type:ignore
            model_used=model_used )


#────────────────────────────────────────── Endpoint 2 ──────────────────────────────────────────


@router.get(
    "/search/stream",
    summary="جستجوی محصول با بازخورد زنده وضعیت (SSE)",
    response_description="جریان رویدادهای text/event-stream",
)
async def search_products_stream(
        query: str,
        request: Request,
        top_k: int = 2,
        session_id: str | None = None,
        client_session_id: str | None = None,
        retriever: QdrantHybridRetriever = Depends( get_retriever ),
        reranker: RerankerService = Depends( get_reranker ),
        llm: LLMOrchestrator = Depends( get_llm ),
        product_repo: ProductRepository = Depends( get_product_repo ),
        service: SearchService = Depends( get_search_service ),
) -> StreamingResponse:
    """‫پردازش کوئری با ارسال زنده وضعیت هر مرحله از پایپلاین.

    ‫رویدادهای SSE ارسالی به ترتیب:
    ‫- ``status`` → وضعیت مرحله جاری (nlu | searching | reranking | generating)
    ‫- ``result`` → پاسخ نهایی کامل (SearchResponse)
    ‫- ``error``  → در صورت بروز خطای غیرمنتظره

    ‫⚠️ این endpoint برای مرورگر و فرانت‌اند طراحی شده.
    ‫فروشگاه‌های B2B باید از POST /search استفاده کنند.
    """
    active_session_id = session_id or str( uuid.uuid4() )
    store_id: str = request.state.store_id

    async def _event_generator() -> AsyncGenerator[ str, None ]:
        t0 = time.perf_counter()
        response_status = "error"
        result_intent = "unknown"
        result_count = 0
        applied_filters: dict | None = None
        tokens: dict = {}
        model_used: str = "unknown"
        try:
            async for event in service.run_streaming(
                    query=query,
                    session_id=active_session_id,
                    top_k=top_k,
            ):
                if isinstance( event, PipelineStatus ):
                    yield _sse_event( "status", { "step": event.step } )

                elif isinstance( event, SearchResponse ):
                    response_status = event.status
                    result_intent = event.intent
                    result_count = len( event.results )
                    applied_filters = dict( event.applied_filters ) if event.applied_filters else None
                    tokens = ( val if isinstance( val := ( event.meta or {} ).get( "token_usage" ), dict ) else {} )
                    model_used = str( event.meta.get( "model_used", "unknown" ) ) if event.meta else "unknown"
                    yield _sse_event( "result", event.model_dump() )

        except Exception:
            log_message( LG.API, f"خطای غیرمنتظره در SSE stream | Query: {query[:50]}", LogLevel.ERROR )
            yield _sse_event( "error", { "message": "خطای داخلی سرور. لطفاً دوباره تلاش کنید." } )

        finally:
            log_query( request_id=uuid.uuid4(),
                       store_id=store_id,
                       user_id=None,
                       session_id=active_session_id,
                       client_session_id=client_session_id,
                       query=query,
                       intent=result_intent,
                       domain="mobile",
                       applied_filters=applied_filters,
                       result_count=result_count,
                       response_status=response_status,
                       latency_ms=int( ( time.perf_counter() - t0 ) * 1000 ),
                       prompt_tokens=tokens.get( "prompt_tokens", 0 ),
                       completion_tokens=tokens.get( "completion_tokens", 0 ),
                       total_tokens=tokens.get( "total_tokens", 0 ),
                       model_used=model_used )

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
