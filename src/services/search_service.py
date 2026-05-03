"""‫سرویس مشترک پایپلاین جستجو (Search Pipeline Service)

‫مسئول: اجرای کامل زنجیره NLU → Retrieval → Rerank → LLM و بازگشت پاسخ نهایی.
‫این ماژول هیچ وابستگی به پروتکل HTTP، SSE یا JSON ندارد و کاملاً Domain-Pure است.
"""
from __future__ import annotations

import asyncio
import time
import uuid
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from src.api.schemas import SearchResponse, SearchResultItem
from src.core.llm.orchestrator import LLMOrchestrator
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.nlu.schemas import NLUFilterQuery
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService

logger = logging.getLogger( __name__ )

# ─────────────────────────────────────────────────────────────────────────────
# مدل وضعیت مرحله — برای SSE endpoint
# ─────────────────────────────────────────────────────────────────────────────


@dataclass( frozen=True )
class PipelineStatus:
    """‫وضعیت لحظه‌ای یک مرحله از پایپلاین (مصرف SSE endpoint)"""
    step: str
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# سرویس اصلی
# ─────────────────────────────────────────────────────────────────────────────


class SearchService:
    """‫اجرای زنجیره کامل جستجو و بازگشت پاسخ ساختاریافته.

    ‫این کلاس protocol-agnostic است:
    ‫- POST endpoint فقط نتیجه نهایی را مصرف می‌کند.
    ‫- SSE endpoint وضعیت مراحل را نیز yield می‌کند.
    """

    # پیام‌های وضعیت هر مرحله
    _STEP_MESSAGES: dict[ str, str ] = {
        "nlu": "در حال پردازش پیام شما...",
        "searching": "در حال جستجو در محصولات...",
        "reranking": "در حال ارزیابی و رتبه‌بندی نتایج...",
        "generating": "در حال آماده‌سازی پاسخ...",
    }

    def __init__(
        self,
        nlu: NLUPipeline,
        retriever: QdrantHybridRetriever,
        reranker: RerankerService,
        llm: LLMOrchestrator,
    ) -> None:
        self._nlu = nlu
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm

    # ─────────────────────────────────────────────────────────────────────────
    # رابط عمومی — اجرای کامل و بازگشت نتیجه (برای POST endpoint)
    # ─────────────────────────────────────────────────────────────────────────

    async def run(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int = 2,
    ) -> tuple[ SearchResponse, int ]:
        """‫اجرای کامل پایپلاین و بازگشت پاسخ نهایی.

        Args:
            query: متن کوئری کاربر
            session_id: شناسه نشست فعال
            top_k: تعداد نتایج درخواستی

        Returns:
            tuple از (SearchResponse, latency_ms)
        """
        result: SearchResponse | None = None
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            if isinstance( event, SearchResponse ):
                result = event

        # pipeline همیشه یک SearchResponse تولید می‌کند
        assert result is not None, "pipeline باید حداقل یک SearchResponse تولید کند"
        latency_ms = int( float( result.meta.get( "latency_ms", 0 ) ) )          #type: ignore
        return result, latency_ms

    # ─────────────────────────────────────────────────────────────────────────
    # رابط عمومی — اجرا با yield وضعیت (برای SSE endpoint)
    # ─────────────────────────────────────────────────────────────────────────

    async def run_streaming(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int = 2,
    ) -> AsyncIterator[ PipelineStatus | SearchResponse ]:
        """‫اجرای پایپلاین با انتشار وضعیت هر مرحله.

        ‫رویدادهای yield‌شده به ترتیب:
        ‫- PipelineStatus × چند بار (یکی به ازای هر مرحله)
        ‫- SearchResponse × یک بار (نتیجه نهایی)

        Args:
            query: متن کوئری کاربر
            session_id: شناسه نشست فعال
            top_k: تعداد نتایج درخواستی

        Yields:
            PipelineStatus یا SearchResponse
        """
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            yield event

    # ─────────────────────────────────────────────────────────────────────────
    # هسته مشترک — پایپلاین کامل
    # ─────────────────────────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int,
    ) -> AsyncIterator[ PipelineStatus | SearchResponse ]:
        """‫اجرای داخلی زنجیره کامل NLU → Retrieval → Rerank → LLM.

        ‫این متد هم توسط run() (POST) و هم run_streaming() (SSE) فراخوانی می‌شود.
        """
        t0 = time.perf_counter()
        req_id = str( uuid.uuid4() )

        # ── مرحله ۱: NLU ─────────────────────────────────────────────────────
        yield PipelineStatus( step="nlu", message=self._STEP_MESSAGES[ "nlu" ] )

        nlu_out: NLUFilterQuery = await asyncio.to_thread( self._nlu.process, query )

        # ── حالت خاص: احوال‌پرسی ─────────────────────────────────────────────
        if nlu_out.is_greeting:
            yield self._build_greeting( req_id=req_id, session_id=session_id, query=query, t0=t0 )
            return

        # ── مرحله ۲: جستجو ───────────────────────────────────────────────────
        yield PipelineStatus( step="searching", message=self._STEP_MESSAGES[ "searching" ] )

        candidates = await asyncio.to_thread(
            self._retriever.search,
            query=nlu_out.semantic_query,
            filters=nlu_out.metadata_filters,
            top_k=max( top_k * 2, 10 ),
        )

        if not candidates:
            yield self._build_empty(
                req_id=req_id,
                session_id=session_id,
                nlu_out=nlu_out,
                t0=t0,
            )
            return

        fallback_steps: int = getattr( self._retriever, "_last_fallback_steps", 0 )

        # ── مرحله ۳: رتبه‌بندی ───────────────────────────────────────────────
        yield PipelineStatus( step="reranking", message=self._STEP_MESSAGES[ "reranking" ] )

        final_products = await asyncio.to_thread(
            self._reranker.rerank,
            query=query,
            payloads=candidates,
            top_k=top_k,
        )

        # ── مرحله ۴: تولید پاسخ LLM ─────────────────────────────────────────
        yield PipelineStatus( step="generating", message=self._STEP_MESSAGES[ "generating" ] )

        llm_out: dict = await self._llm.generate(
            session_id=session_id,
            user_query=query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
        )

        # ── ساخت پاسخ نهایی ──────────────────────────────────────────────────
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
        status = "partial" if fallback_steps > 0 else "success"

        yield SearchResponse(
            status=status,
            request_id=req_id,
            session_id=session_id,
            intent=nlu_out.intent,
            semantic_query=nlu_out.semantic_query,
            applied_filters=nlu_out.metadata_filters if nlu_out else {},
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

    # ─────────────────────────────────────────────────────────────────────────
    # سازنده‌های پاسخ‌های خاص
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _build_greeting( *, req_id: str, session_id: str, query: str, t0: float ) -> SearchResponse:
        """‫ساخت پاسخ احوال‌پرسی"""
        return SearchResponse(
            status="success",
            request_id=req_id,
            session_id=session_id,
            intent="greeting",
            semantic_query=query,
            applied_filters={},
            results=[],
            message="سلام! چطور می‌تونم کمکتون کنم؟",
            llm_explanation="",
            next_suggestion="نیازتان را بنویسید.",
            meta={ "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ) },
        )

    @staticmethod
    def _build_empty(
        *,
        req_id: str,
        session_id: str,
        nlu_out: NLUFilterQuery,
        t0: float,
    ) -> SearchResponse:
        """‫ساخت پاسخ خالی (صفر نتیجه)"""
        return SearchResponse(
            status="empty",
            request_id=req_id,
            session_id=session_id,
            intent=nlu_out.intent,
            semantic_query=nlu_out.semantic_query,
            applied_filters=nlu_out.metadata_filters if nlu_out else {},
            results=[],
            message="متأسفانه محصولی با این مشخصات پیدا نشد.",
            llm_explanation="",
            next_suggestion="فیلترها را کمی گسترده‌تر کنید یا برند/قیمت را تغییر دهید.",
            meta={
                "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ),
                "fallback_steps": 0,
                "total_candidates": 0,
            },
        )
