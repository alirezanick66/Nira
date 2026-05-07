"""‫سرویس مشترک پایپلاین جستجو (Search Pipeline Service)

‫مسئول: اجرای کامل زنجیره NLU → Retrieval → Rerank → LLM و بازگشت پاسخ نهایی.
‫این ماژول هیچ وابستگی به پروتکل HTTP، SSE یا JSON ندارد و کاملاً Domain-Pure است.
"""
from __future__ import annotations

import asyncio
import time
import uuid
import logging
import random
from typing import AsyncGenerator

from src.api.schemas import PipelineStatus, SearchResponse, SearchResultItem
from src.core.llm.orchestrator import LLMOrchestrator
from src.core.nlu.llm_extractor import LLMNLUExtractor
from src.core.nlu.schemas import NLUFilterQuery
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.data.repositories.product_repository import ProductRepository
from src.config.logging_config import log_message, LogLevel, LG

logger = logging.getLogger( __name__ )


class SearchService:
    """‫اجرای زنجیره کامل جستجو و بازگشت پاسخ ساختاریافته.

    ‫این کلاس protocol-agnostic است:
    ‫- POST endpoint فقط نتیجه نهایی را مصرف می‌کند.
    ‫- SSE endpoint وضعیت مراحل را نیز yield می‌کند.
    """

    _STEP_MESSAGES: dict[ str, str ] = {
        "nlu": "در حال پردازش پیام شما...",
        "searching": "در حال جستجو در محصولات...",
        "reranking": "در حال ارزیابی و رتبه‌بندی نتایج...",
        "generating": "در حال آماده‌سازی پاسخ...",
    }

    def __init__(
        self,
        nlu: LLMNLUExtractor,
        retriever: QdrantHybridRetriever,
        reranker: RerankerService,
        llm: LLMOrchestrator,
        image_repo: ProductRepository | None = None,
    ) -> None:
        self._nlu = nlu
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm
        self._image_repo = image_repo

    # ─────────────────────────────────────────────────────────────────────────
    # رابط عمومی
    # ─────────────────────────────────────────────────────────────────────────

    async def run( self, *, query: str, session_id: str, top_k: int = 2 ) -> tuple[ SearchResponse, int ]:
        """‫اجرای کامل پایپلاین و بازگشت پاسخ نهایی (برای POST endpoint)"""
        result: SearchResponse | None = None
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            if isinstance( event, SearchResponse ):
                result = event

        if result is None:
            raise RuntimeError( "pipeline باید حداقل یک SearchResponse تولید کند" )

        latency_ms = int( float( result.meta.get( "latency_ms", 0 ) ) )          # type: ignore
        return result, latency_ms

    async def run_streaming( self,
                             *,
                             query: str,
                             session_id: str,
                             top_k: int = 2 ) -> AsyncGenerator[ PipelineStatus | SearchResponse, None ]:
        """‫اجرای پایپلاین با انتشار وضعیت هر مرحله (برای SSE endpoint)"""
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            yield event

    # ─────────────────────────────────────────────────────────────────────────
    # هسته مشترک
    # ─────────────────────────────────────────────────────────────────────────

    async def _run_pipeline( self, *, query: str, session_id: str,
                             top_k: int ) -> AsyncGenerator[ PipelineStatus | SearchResponse, None ]:
        """‫اجرای داخلی زنجیره کامل NLU → Retrieval → Rerank → LLM"""
        t0 = time.perf_counter()
        req_id = str( uuid.uuid4() )

        # ── مرحله ۱: NLU ─────────────────────────────────────────────────────
        yield PipelineStatus( step="nlu", message=self._STEP_MESSAGES[ "nlu" ] )
        nlu_out: NLUFilterQuery = await self._nlu.extract( query, session_id )

        if nlu_out.is_greeting:
            yield self._build_greeting( req_id=req_id, session_id=session_id, query=query, t0=t0 )
            return

        # ── ادغام فیلترهای refine ─────────────────────────────────────────────
        effective_filters = await self._llm.memory.merge_refine_filters(
            intent=nlu_out.intent,
            new_filters=dict( nlu_out.metadata_filters ),
            session_id=session_id,
            sort_directive=nlu_out.sort_directive,
        )
        log_message( LG.LLM, f"🔀 فیلترهای مؤثر | Intent: {nlu_out.intent} | Filters: {effective_filters}", LogLevel.DEBUG )

        # ── مرحله ۲: جستجو ───────────────────────────────────────────────────
        yield PipelineStatus( step="searching", message=self._STEP_MESSAGES[ "searching" ] )
        candidates, fallback_steps = await self._resolve_candidates( nlu_out, effective_filters, top_k )

        if not candidates:
            yield self._build_empty( req_id=req_id, session_id=session_id, nlu_out=nlu_out, t0=t0 )
            return

        # ── مرحله ۳: رتبه‌بندی ───────────────────────────────────────────────
        yield PipelineStatus( step="reranking", message=self._STEP_MESSAGES[ "reranking" ] )
        final_products = await asyncio.to_thread( self._reranker.rerank, query=query, payloads=candidates, top_k=top_k )
        await self._enrich_products( final_products )

        # ── مرحله ۴: تولید پاسخ LLM ─────────────────────────────────────────
        yield PipelineStatus( step="generating", message=self._STEP_MESSAGES[ "generating" ] )
        llm_out: dict = await self._llm.generate(
            session_id=session_id,
            user_query=query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
            applied_filters=effective_filters,
        )

        yield self._build_final_response(
            req_id=req_id,
            session_id=session_id,
            nlu_out=nlu_out,
            effective_filters=effective_filters,
            candidates=candidates,
            final_products=final_products,
            llm_out=llm_out,
            t0=t0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # متدهای خصوصی
    # ─────────────────────────────────────────────────────────────────────────

    async def _resolve_candidates(
        self,
        nlu_out: NLUFilterQuery,
        effective_filters: dict,
        top_k: int,
    ) -> tuple[ list[ QdrantProductPayload ], int ]:
        """‫بازیابی کاندیداها با مدیریت کوئری کوتاه و closest-available fallback"""
        retrieve_query = nlu_out.semantic_query
        if nlu_out.intent == "refine" and len( retrieve_query.replace( " ", "" ) ) < 4:
            retrieve_query = "گوشی موبایل جدید"
            log_message( LG.LLM, "🌱 کوئری refine کوتاه → تزریق Seed دامنه", LogLevel.DEBUG )

        candidates: list[ QdrantProductPayload ] = await asyncio.to_thread(
            self._retriever.search,
            query=retrieve_query,
            filters=effective_filters,
            top_k=max( top_k * 2, 10 ),
        )

        fallback_steps: int = getattr( self._retriever, "_last_fallback_steps", 0 )
        if fallback_steps > 0 and candidates:
            candidates = self._apply_closest_available( candidates, effective_filters )
        fallback_steps = getattr( self._retriever, "_last_fallback_steps", 0 )
        return candidates, fallback_steps

    @staticmethod
    def _apply_closest_available(
        candidates: list[ QdrantProductPayload ],
        filters: dict,
    ) -> list[ QdrantProductPayload ]:
        """‫مرتب‌سازی کاندیداها بر اساس نزدیک‌ترین مقدار به فیلتر عددی در صورت fallback"""
        for field_name, constraint in filters.items():
            if not isinstance( constraint, dict ):
                continue
            op, target = next( iter( constraint.items() ) )
            has_match = any( ( v := getattr( c, field_name, None ) ) is not None and ( ( op == ">=" and v >= target ) or (
                op == "<=" and v <= target ) or ( op == ">" and v > target ) or ( op == "<" and v < target ) ) for c in candidates )
            if not has_match:
                reverse = op in ( ">=", ">" )
                candidates.sort( key=lambda p: getattr( p, field_name, 0 ) or 0, reverse=reverse )
                log_message(
                    LG.RETRIEVAL,
                    f"🎯 نزدیک‌ترین گزینه | {field_name} {op} {target} → {getattr(candidates[0], field_name, 'N/A')}",
                    LogLevel.INFO,
                )
                break
        return candidates

    async def _enrich_products( self, products: list[ QdrantProductPayload ] ) -> None:
        """‫واکشی image_url از PostgreSQL و لاگ محصولات نهایی"""
        if self._image_repo and products:
            ids = [ p.product_id for p in products ]
            url_map = await self._image_repo.batch_get_image_urls( ids )
            for p in products:
                if hasattr( p, "image_url" ):
                    p.image_url = url_map.get( p.product_id )

        if products:
            summary = [ f"{p.title[:40]}... | {p.price:,.0f} تومان" for p in products[ :2 ] ]
            log_message( LG.LLM, f"{summary}", LogLevel.DEBUG )

    def _build_final_response(
        self,
        req_id: str,
        session_id: str,
        nlu_out: NLUFilterQuery,
        effective_filters: dict,
        candidates: list[ QdrantProductPayload ],
        final_products: list[ QdrantProductPayload ],
        llm_out: dict,
        t0: float,
    ) -> SearchResponse:
        """‫ساخت SearchResponse نهایی از خروجی تمام مراحل پایپلاین"""
        fallback_steps: int = getattr( self._retriever, "_last_fallback_steps", 0 )
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
        return SearchResponse(
            status="partial" if fallback_steps > 0 else "success",
            request_id=req_id,
            session_id=session_id,
            intent=nlu_out.intent,
            semantic_query=nlu_out.semantic_query,
            applied_filters=effective_filters,
            results=results,
            message=str( llm_out.get( "explanation", "" ) ),
            llm_explanation=str( llm_out.get( "explanation", "" ) ),
            next_suggestion=str( llm_out.get( "next_suggestion", "" ) ),
            meta={
                "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ),
                "fallback_steps": fallback_steps,
                "total_candidates": len( candidates ),
            },
        )

    def _build_greeting( self, *, req_id: str, session_id: str, query: str, t0: float ) -> SearchResponse:
        """‫ساخت پاسخ احوال‌پرسی از کانفیگ دامنه"""
        responses: list[ str ] = self._nlu.greeting_responses
        return SearchResponse(
            status="success",
            request_id=req_id,
            session_id=session_id,
            intent="greeting",
            semantic_query=query,
            applied_filters={},
            results=[],
            message=random.choice( responses ),
            llm_explanation="",
            next_suggestion="نیازتان را بنویسید.",
            meta={ "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ) },
        )

    @staticmethod
    def _build_empty( *, req_id: str, session_id: str, nlu_out: NLUFilterQuery, t0: float ) -> SearchResponse:
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
                "total_candidates": 0
            },
        )
