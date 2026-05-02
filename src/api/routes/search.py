"""روتر اختصاصی جستجوی محصولات (نسخه B2B استاندارد + SSE Streaming)"""
#───────────────────── Imports ─────────────────────
import uuid
import time
import json
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

#───────────────────── Local Imports ─────────────────────
from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator
from src.api.dependencies import get_nlu_pipeline, get_retriever, get_reranker, get_llm
from src.config.logging_config import log_message, LogLevel, LG
from src.services.query_log_service import log_query

router = APIRouter( prefix="/api/v1", tags=[ "Search" ] )

# ─────────────────────────────────────────────────────────────────────────────
# ابزار کمکی: فرمت‌بندی رویداد SSE
# ─────────────────────────────────────────────────────────────────────────────


def _sse_event( event: str, data: dict ) -> str:
    """‫یک رویداد SSE استاندارد را با نوع و داده JSON فرمت می‌کند"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint اصلی: جستجوی استریم‌شده با SSE
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
        user_id: str | None = None,
        client_session_id: str | None = None,
        nlu: NLUPipeline = Depends( get_nlu_pipeline ),
        retriever: QdrantHybridRetriever = Depends( get_retriever ),
        reranker: RerankerService = Depends( get_reranker ),
        llm: LLMOrchestrator = Depends( get_llm ),
) -> StreamingResponse:
    """
    ‫پردازش کوئری کاربر با ارسال زنده وضعیت هر مرحله از pipeline.

    رویدادهای ارسالی به ترتیب:
    - ``status``  → وضعیت مرحله جاری (nlu | searching | reranking | generating)
    - ``result``  → پاسخ نهایی کامل (SearchResponse بدون فیلد meta حساس)
    - ``error``   → در صورت بروز خطای غیرمنتظره
    """
    active_session_id = session_id or str( uuid.uuid4() )
    store_id = request.state.store_id

    async def _event_generator() -> AsyncGenerator[ str, None ]:
        t0 = time.perf_counter()
        req_id = str( uuid.uuid4() )
        response_status = "error"
        result_count = 0
        nlu_out = None

        try:
            # ── مرحله ۱: پردازش NLU ──────────────────────────────────────────
            yield _sse_event( "status", { "step": "nlu", "message": "در حال پردازش پیام شما..." } )

            nlu_out = await asyncio.to_thread( nlu.process, query )

            # ── حالت خاص: احوال‌پرسی ──────────────────────────────────────────
            if nlu_out.is_greeting:
                response_status = "success"
                payload = SearchResponse(
                    status="success",
                    request_id=req_id,
                    session_id=active_session_id,
                    intent="greeting",
                    semantic_query=query,
                    applied_filters={},
                    results=[],
                    message="سلام! چطور می‌تونم کمکتون کنم؟",
                    llm_explanation="",
                    next_suggestion="نیازتان را بنویسید.",
                    meta={ "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ) },
                )
                yield _sse_event( "result", payload.model_dump() )
                return

            # ── مرحله ۲: جستجو در محصولات ────────────────────────────────────
            yield _sse_event( "status", { "step": "searching", "message": "در حال جستجو در محصولات..." } )

            candidates = await asyncio.to_thread(
                retriever.search,
                query=nlu_out.semantic_query,
                filters=nlu_out.metadata_filters,
                top_k=max( top_k * 2, 10 ),
            )

            if not candidates:
                latency = round( ( time.perf_counter() - t0 ) * 1000, 1 )
                response_status = "empty"
                payload = SearchResponse(
                    status="empty",
                    request_id=req_id,
                    session_id=active_session_id,
                    intent=nlu_out.intent,
                    semantic_query=nlu_out.semantic_query,
                    applied_filters=nlu_out.metadata_filters,
                    results=[],
                    message="متأسفانه محصولی با این مشخصات پیدا نشد.",
                    llm_explanation="",
                    next_suggestion="فیلترها را کمی گسترده‌تر کنید یا برند/قیمت را تغییر دهید.",
                    meta={
                        "latency_ms": latency,
                        "fallback_steps": 0,
                        "total_candidates": 0
                    },
                )
                yield _sse_event( "result", payload.model_dump() )
                return

            fallback_steps = getattr( retriever, "_last_fallback_steps", 0 )

            # ── مرحله ۳: رتبه‌بندی نهایی ─────────────────────────────────────
            yield _sse_event( "status", { "step": "reranking", "message": "در حال ارزیابی و رتبه‌بندی نتایج..." } )

            final_products = await asyncio.to_thread(
                reranker.rerank,
                query=query,
                payloads=candidates,
                top_k=top_k,
            )

            # ── مرحله ۴: تولید پاسخ با LLM ──────────────────────────────────
            yield _sse_event( "status", { "step": "generating", "message": "در حال آماده‌سازی پاسخ..." } )

            llm_out = await llm.generate(
                session_id=active_session_id,
                user_query=query,
                intent=nlu_out.intent,
                filters_str=str( nlu_out.metadata_filters ),
                products=final_products,
            )

            results = [
                SearchResultItem(
                    product_id=p.product_id,
                    title=p.title,
                    price=p.price,
                    price_range=p.price_range or "نامشخص",
                    camera_quality=p.camera_quality or "نامشخص",
                    tags=p.tags or [],
                    image_url=p.image_url,
                    relevance_score=getattr( p, "rerank_score", 0.0 ),
                ) for p in final_products
            ]

            latency_ms = round( ( time.perf_counter() - t0 ) * 1000, 1 )
            response_status = "partial" if fallback_steps > 0 else "success"
            result_count = len( results )

            payload = SearchResponse(
                status=response_status,
                request_id=req_id,
                session_id=active_session_id,
                intent=nlu_out.intent,
                semantic_query=nlu_out.semantic_query,
                applied_filters=nlu_out.metadata_filters,
                results=results,
                message=str( llm_out.get( "explanation", "" ) ),
                llm_explanation=str( llm_out.get( "explanation", "" ) ),
                next_suggestion=str( llm_out.get( "next_suggestion", "" ) ),
                meta={
                    "latency_ms": latency_ms,
                    "fallback_steps": fallback_steps,
                    "total_candidates": len( candidates ),
                },
            )
            yield _sse_event( "result", payload.model_dump() )

        except Exception as exc:
            log_message( LG.API, f"خطای غیرمنتظره در SSE stream: {exc}", LogLevel.ERROR )
            yield _sse_event( "error", { "message": "خطای داخلی سرور. لطفاً دوباره تلاش کنید." } )

        finally:
            log_query(
                request_id=uuid.UUID( req_id ),
                store_id=store_id,
                user_id=user_id,
                session_id=active_session_id,
                client_session_id=client_session_id,
                query=query,
                intent=nlu_out.intent if nlu_out else "unknown",
                domain="mobile",
                applied_filters=nlu_out.metadata_filters if nlu_out else None,
                result_count=result_count,
                response_status=response_status,
                latency_ms=int( ( time.perf_counter() - t0 ) * 1000 ),
            )

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",          # غیرفعال‌سازی بافرینگ Nginx
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint قدیمی: حفظ سازگاری معکوس (Backward Compatible)
# ─────────────────────────────────────────────────────────────────────────────


@router.post( "/search", response_model=SearchResponse, status_code=status.HTTP_200_OK )
async def search_products(
        request_body: SearchRequest,
        request: Request,
        nlu: NLUPipeline = Depends( get_nlu_pipeline ),
        retriever: QdrantHybridRetriever = Depends( get_retriever ),
        reranker: RerankerService = Depends( get_reranker ),
        llm: LLMOrchestrator = Depends( get_llm ),
) -> SearchResponse:
    """پردازش کوئری کاربر و بازگرداندن پاسخ استاندارد ساختاریافته (بدون streaming)"""
    t0 = time.perf_counter()
    req_id = str( uuid.uuid4() )
    session_id = request.client_session_id or str( uuid.uuid4() )          #type: ignore
    store_id = request.state.store_id
    response_status = "error"
    result_count = 0
    nlu_out = None

    try:
        nlu_out = nlu.process( request_body.query )

        if nlu_out.is_greeting:
            response_status = "success"
            return SearchResponse(
                status="success",
                request_id=req_id,
                session_id=session_id,
                intent="greeting",
                semantic_query=request_body.query,
                applied_filters={},
                results=[],
                message="سلام! چطور می‌تونم کمکتون کنم؟",
                llm_explanation="",
                next_suggestion="نیازتان را بنویسید.",
                meta={ "latency_ms": 0.0 },
            )

        candidates = await asyncio.to_thread(
            retriever.search,
            query=nlu_out.semantic_query,
            filters=nlu_out.metadata_filters,
            top_k=max( request_body.top_k * 2, 10 ),
        )

        if not candidates:
            latency = round( ( time.perf_counter() - t0 ) * 1000, 1 )
            response_status = "empty"
            return SearchResponse(
                status="empty",
                request_id=req_id,
                session_id=session_id,
                intent=nlu_out.intent,
                semantic_query=nlu_out.semantic_query,
                applied_filters=nlu_out.metadata_filters,
                results=[],
                message="متأسفانه محصولی با این مشخصات پیدا نشد.",
                llm_explanation="",
                next_suggestion="فیلترها را کمی گسترده‌تر کنید یا برند/قیمت را تغییر دهید.",
                meta={
                    "latency_ms": latency,
                    "fallback_steps": 0,
                    "total_candidates": 0
                },
            )

        fallback_steps = getattr( retriever, "_last_fallback_steps", 0 )
        response_status = "partial" if fallback_steps > 0 else "success"

        final_products = await asyncio.to_thread(
            reranker.rerank,
            query=request_body.query,
            payloads=candidates,
            top_k=request_body.top_k,
        )

        llm_out = await llm.generate(
            session_id=session_id,
            user_query=request_body.query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
        )

        results = [
            SearchResultItem(
                product_id=p.product_id,
                title=p.title,
                price=p.price,
                price_range=p.price_range or "نامشخص",
                camera_quality=p.camera_quality or "نامشخص",
                tags=p.tags or [],
                image_url=p.image_url,
                relevance_score=getattr( p, "rerank_score", 0.0 ),
            ) for p in final_products
        ]

        latency_ms = round( ( time.perf_counter() - t0 ) * 1000, 1 )
        result_count = len( results )

        return SearchResponse(
            status=response_status,
            request_id=req_id,
            session_id=session_id,
            intent=nlu_out.intent,
            semantic_query=nlu_out.semantic_query,
            applied_filters=nlu_out.metadata_filters,
            results=results,
            message=str( llm_out.get( "explanation", "" ) ),
            llm_explanation=str( llm_out.get( "explanation", "" ) ),
            next_suggestion=str( llm_out.get( "next_suggestion", "" ) ),
            meta={
                "latency_ms": latency_ms,
                "fallback_steps": fallback_steps,
                "total_candidates": len( candidates ),
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در Endpoint جستجو: {exc}", LogLevel.ERROR )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطای داخلی سرور.",
        )

    finally:
        log_query(
            request_id=uuid.UUID( req_id ),
            store_id=store_id,
            user_id=getattr( request_body, "user_id", None ),
            session_id=session_id,
            client_session_id=getattr( request_body, "client_session_id", None ),
            query=request_body.query,
            intent=nlu_out.intent if nlu_out else "unknown",
            domain=getattr( request_body, "domain", "mobile" ),
            applied_filters=nlu_out.metadata_filters if nlu_out else None,
            result_count=result_count,
            response_status=response_status,
            latency_ms=int( ( time.perf_counter() - t0 ) * 1000 ),
        )
