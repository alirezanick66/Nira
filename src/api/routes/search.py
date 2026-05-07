"""‫روتر اختصاصی جستجوی محصولات

‫این ماژول فقط مسئول:
‫۱. دریافت درخواست HTTP (POST یا GET/SSE)
‫۲. تفویض کامل منطق به SearchService
‫۳. لاگ‌گیری هر درخواست (cross-cutting concern)
‫است و هیچ منطق تجاری مستقیمی ندارد.
"""

#─────────────────────imports─────────────────────
from __future__ import annotations
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

#─────────────────────local imports─────────────────────
from src.data.repositories.product_repository import ProductRepository
from src.api.schemas import SearchRequest, SearchResponse
from src.services.search_service import PipelineStatus, SearchService
from src.api.dependencies import get_retriever, get_reranker, get_llm, get_product_repo
from src.services.query_log_service import log_query

if TYPE_CHECKING:
    from src.core.llm.orchestrator import LLMOrchestrator
    from src.core.vector.qdrant_retriever import QdrantHybridRetriever
    from src.services.reranker_service import RerankerService

logger = logging.getLogger( __name__ )

router = APIRouter( prefix="/api/v1", tags=[ "Search" ] )

# ─────────────────────────────────────────────────────────────────────────────
# ابزار کمکی: ساخت SearchService از وابستگی‌های تزریق‌شده
# ─────────────────────────────────────────────────────────────────────────────


def _build_service(
    retriever: QdrantHybridRetriever,
    reranker: RerankerService,
    llm: LLMOrchestrator,
    product_repo: ProductRepository,
) -> SearchService:
    """‫ساخت نمونه SearchService از وابستگی‌های FastAPI"""
    return SearchService( retriever=retriever, reranker=reranker, llm=llm, image_repo=product_repo )


# ─────────────────────────────────────────────────────────────────────────────
# ابزار کمکی: فرمت‌بندی رویداد SSE
# ─────────────────────────────────────────────────────────────────────────────


def _sse_event( event: str, data: dict ) -> str:
    """‫فرمت‌بندی یک رویداد SSE استاندارد"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1: جستجوی B2B (قرارداد رسمی فروشگاه‌ها)
# ─────────────────────────────────────────────────────────────────────────────


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
        service = _build_service( retriever, reranker, llm, product_repo )
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
        logger.exception( "خطای پیش‌بینی‌نشده در POST /search" )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطای داخلی سرور.",
        )
    finally:
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
        )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2: جستجوی SSE (فرانت‌اند و UX لحظه‌ای)
# ─────────────────────────────────────────────────────────────────────────────


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
    product_repo: ProductRepository = Depends( get_product_repo )
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

        try:
            service = _build_service( retriever, reranker, llm, product_repo )

            async for event in service.run_streaming(
                    query=query,
                    session_id=active_session_id,
                    top_k=top_k,
            ):
                if isinstance( event, PipelineStatus ):
                    yield _sse_event( "status", { "step": event.step, "message": event.message } )

                elif isinstance( event, SearchResponse ):
                    response_status = event.status
                    result_intent = event.intent
                    result_count = len( event.results )
                    applied_filters = json.loads( json.dumps( dict( event.applied_filters ), ensure_ascii=False ) )
                    yield _sse_event( "result", event.model_dump() )

        except Exception:
            logger.exception( "خطای غیرمنتظره در SSE stream" )
            yield _sse_event( "error", { "message": "خطای داخلی سرور. لطفاً دوباره تلاش کنید." } )

        finally:
            log_query(
                request_id=uuid.uuid4(),
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
            )

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
