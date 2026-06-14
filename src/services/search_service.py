""" ‫‫سرویس مشترک پایپلاین جستجو (نسخه LLM-Based)
‫مسئول: اجرای کامل زنجیره Extract(LLM) → Retrieval → Rerank → LLM و بازگشت پاسخ نهایی.
‫این ماژول هیچ وابستگی به پروتکل HTTP، SSE یا JSON ندارد و کاملاً Domain-Pure است.
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import asyncio
import time
import uuid
import json
import random
from typing import AsyncGenerator
from enum import StrEnum
#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.core.schemas import PipelineStatus, SearchResponse, SearchResultItem
from src.core.llm.orchestrator import LLMOrchestrator
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.core.llm.schemas import IntentType, MetadataFilters, LLMExtractSchema
from src.services.reranker_service import RerankerService
from src.data.repositories.product_repository import ProductRepository
from src.config.logging_config import log_message, LogLevel, LG


class SearchService:
    """‫اجرای زنجیره کامل جستجو و بازگشت پاسخ ساختاریافته.

    ‫این کلاس protocol-agnostic است:
    ‫- POST endpoint فقط نتیجه نهایی را مصرف می‌کند.
    ‫- SSE endpoint وضعیت مراحل را نیز yield می‌کند.
    """

    class PipelineStep( StrEnum ):
        EXTRACT = "extract"
        SEARCHING = "searching"
        RERANKING = "reranking"
        GENERATING = "generating"

    def __init__(
        self,
        retriever: QdrantHybridRetriever,
        reranker: RerankerService,
        llm: LLMOrchestrator,
        image_repo: ProductRepository | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm
        self._image_repo = image_repo

    # ─────────────────────────────────────────────────────────────────────────
    # رابط عمومی
    # ─────────────────────────────────────────────────────────────────────────

    async def run( self, *, query: str, session_id: str, top_k: int = 2 ) -> tuple[ SearchResponse, float ]:
        """‫اجرای کامل پایپلاین و بازگشت پاسخ نهایی (برای POST endpoint)"""
        result: SearchResponse | None = None
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            if isinstance( event, SearchResponse ):
                result = event

        if result is None:
            raise RuntimeError( "pipeline باید حداقل یک SearchResponse تولید کند" )

        latency_ms = float( result.meta.get( "latency_ms", 0 ) )          # type: ignore
        return result, latency_ms

    async def run_streaming(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int = 2,
    ) -> AsyncGenerator[ PipelineStatus | SearchResponse, None ]:
        """‫اجرای پایپلاین با انتشار وضعیت هر مرحله (برای SSE endpoint)"""
        async for event in self._run_pipeline( query=query, session_id=session_id, top_k=top_k ):
            yield event

    # ─────────────────────────────────────────────────────────────────────────
    # هسته مشترک
    # ─────────────────────────────────────────────────────────────────────────

    async def _run_pipeline(
        self,
        *,
        query: str,
        session_id: str,
        top_k: int,
    ) -> AsyncGenerator[ PipelineStatus | SearchResponse, None ]:
        """‫اجرای داخلی زنجیره کامل Extract → Retrieval → Rerank → LLM"""
        t0 = time.perf_counter()
        req_id = str( uuid.uuid4() )

        # ── مرحله ۱: استخراج نیت و فیلتر (LLM Extract + Fast Greeting) ─────
        yield PipelineStatus( step=self.PipelineStep.EXTRACT )

        last_filters = await self._llm.get_session_last_filters( session_id )
        history = await self._llm.get_session_history( session_id )
        extract_result: LLMExtractSchema = await self._llm.extract(
            query=query,
            session_id=session_id,
            last_filters=last_filters,
            last_products=None,          # 🔹 در فازهای بعدی از حافظه خوانده می‌شود
            history=history,
        )

        # ‫🔹 مدیریت Intentهای خاص قبل از ورود به پایپلاین جستجو
        if extract_result.intent in ( IntentType.GREETING, IntentType.GENERAL_CHAT ):
            greeting_response = self._build_greeting(
                req_id=req_id,
                session_id=session_id,
                query=query,
                intent=extract_result.intent.value,
                t0=t0,
            )
            await self._llm.save_turn(
                session_id=session_id,
                user_msg=query,
                assistant_msg=greeting_response.message,
            )
            yield greeting_response
            return

        if extract_result.needs_clarification:
            clarification_response = self._build_clarification(
                req_id=req_id,
                session_id=session_id,
                query=query,
                question=extract_result.clarification_question,
                t0=t0,
            )
            await self._llm.save_turn(
                session_id=session_id,
                user_msg=query,
                assistant_msg=clarification_response.message,
            )
            yield clarification_response
            return

        if extract_result.has_conflict:
            log_message( LG.LLM, f"⚠️ تضاد فیلتر شناسایی شد: {extract_result.conflict_reason}", LogLevel.WARNING )

        log_message( LG.LLM, f"🔀 فیلترهای مؤثر | Intent: {extract_result.intent} | Filters: {extract_result.metadata_filters}",
                     LogLevel.DEBUG )

        # ── مرحله ۲: جستجو ────────────────────────────────────────────────
        yield PipelineStatus( step=self.PipelineStep.SEARCHING )
        candidates, fallback_steps = await self._resolve_candidates(
            semantic_query=extract_result.semantic_query,
            filters=extract_result.metadata_filters,
            top_k=top_k,
        )

        if not candidates:
            yield self._build_empty( req_id=req_id, session_id=session_id, extract_out=extract_result, t0=t0 )
            return

        # ── مرحله ۳: رتبه‌بندی ───────────────────────────────────────────────
        yield PipelineStatus( step=self.PipelineStep.RERANKING )
        # جلوگیری از برش زودهنگام توسط Reranker برای اعمال صحیح مرتب‌سازی
        print( top_k )
        final_products = await asyncio.to_thread( self._reranker.rerank, query=query, payloads=candidates, top_k=len( candidates ) )
        await self._enrich_products( final_products )

        # 🔧 ۲. تشخیص نیت‌های ترتیبی (گرون‌ترین/ارزون‌ترین) و مرتب‌سازی
        filters = extract_result.metadata_filters
        floor_price = filters.get( "price", {} ).get( ">" ) or filters.get( "price", {} ).get( ">=" )          # type: ignore

        if extract_result.sort_order == "price_desc":
            final_products.sort( key=lambda p: p.price, reverse=True )
            log_message( LG.LLM, "📉 مرتب‌سازی نزولی بر اساس قیمت (گران‌ترین/لوکس‌ترین) اعمال شد.", LogLevel.DEBUG )
        elif extract_result.sort_order == "price_asc":
            final_products.sort( key=lambda p: p.price )
            log_message( LG.LLM, "📉 مرتب‌سازی صعودی بر اساس قیمت (ارزان‌ترین) اعمال شد.", LogLevel.DEBUG )
        elif floor_price:
            final_products.sort( key=lambda p: abs( p.price - floor_price ) )
            log_message( LG.LLM, "📉 مرتب‌سازی بر اساس نزدیکی به کف قیمت انجام شد.", LogLevel.DEBUG )

        # محدودسازی نهایی برای ارسال به LLM
        final_products = final_products[ :top_k ]

        # ── مرحله ۴: تولید پاسخ LLM ─────────────────────────────────────────
        yield PipelineStatus( step=self.PipelineStep.GENERATING )

        user_budget = extract_result.metadata_filters.get( "price", {} ).get( "<=" )          # type: ignore
        min_price = min( ( p.price for p in final_products ), default=0 )

        filters_str = json.dumps( extract_result.metadata_filters, ensure_ascii=False, indent=2 )
        llm_out: dict = await self._llm.generate(
            session_id=session_id,
            user_query=query,
            intent=extract_result.intent.value,
            filters_str=filters_str,
            products=final_products,
            applied_filters=extract_result.metadata_filters,
            user_budget=user_budget,
            min_price=min_price,
        )

        yield self._build_final_response(
            req_id=req_id,
            session_id=session_id,
            extract_out=extract_result,
            effective_filters=extract_result.metadata_filters,
            candidates=candidates,
            final_products=final_products,
            llm_out=llm_out,
            t0=t0,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # متدهای خصوصی
    # ─────────────────────────────────────────────────────────────────────────

    async def _resolve_candidates( self, semantic_query: str, filters: MetadataFilters | None,
                                   top_k: int ) -> tuple[ list[ QdrantProductPayload ], int ]:
        """‫بازیابی کاندیداها با مدیریت کوئری کوتاه و fallback"""
        retrieve_query = semantic_query
        if len( retrieve_query.strip() ) < 3:
            retrieve_query = "گوشی موبایل جدید"
            log_message( LG.RETRIEVAL, "🌱 کوئری معنایی کوتاه → تزریق Seed دامنه", LogLevel.DEBUG )

        candidates: list[ QdrantProductPayload ] = await asyncio.to_thread( self._retriever.search,
                                                                            query=retrieve_query,
                                                                            filters=filters,
                                                                            top_k=max( top_k * 2, 10 ) )

        fallback_steps: int = self._retriever._last_fallback_steps
        return candidates, fallback_steps

    async def _enrich_products( self, products: list[ QdrantProductPayload ] ) -> None:
        """‫واکشی image_url از PostgreSQL و لاگ محصولات نهایی"""
        if self._image_repo and products:
            ids = [ p.product_id for p in products ]
            url_map = await self._image_repo.batch_get_image_urls( ids )
            for p in products:
                p.image_url = url_map.get( p.product_id )

        if products:
            summary = [ f"{p.title[:40]}... | {p.price:,.0f} تومان" for p in products[ :2 ] ]
            log_message( LG.LLM, f"📦 محصولات نهایی: {summary}", LogLevel.DEBUG )

    @staticmethod
    def _select_llm_products(
        final_products: list[ QdrantProductPayload ],
        llm_out: dict,
    ) -> list[ QdrantProductPayload ]:
        """‫انتخاب محصولات نهایی برای نمایش بر اساس product_ids تأییدشدهٔ LLM

        ‫منطق ایمن (Fail-Safe):
        ‫- ترتیب انتخاب LLM حفظ می‌شود (ممکن است معنادار باشد).
        ‫- اگر product_ids خالی/ناموجود باشد یا هیچ‌کدام با محصولات منطبق نشوند،
        ‫  به رفتار قبلی (همهٔ محصولات reranked) بازمی‌گردیم تا پاسخ هرگز بی‌دلیل خالی نشود.

        Args:
            final_products: محصولات نهایی پس از reranking
            llm_out: خروجی اعتبارسنجی‌شدهٔ LLM (شامل product_ids)

        Returns:
            لیست محصولات منتخب برای ساخت results
        """
        raw_ids = llm_out.get( "product_ids" )
        if not isinstance( raw_ids, list ) or not raw_ids:
            return final_products

        # ‫نرمال‌سازی شناسه‌ها به int و حذف موارد نامعتبر/تکراری با حفظ ترتیب
        seen: set[ int ] = set()
        allowed_ids: list[ int ] = []
        for rid in raw_ids:
            try:
                pid = int( rid )
            except ( TypeError, ValueError ):
                continue
            if pid not in seen:
                seen.add( pid )
                allowed_ids.append( pid )

        if not allowed_ids:
            return final_products

        by_id = { p.product_id: p for p in final_products }
        selected = [ by_id[ pid ] for pid in allowed_ids if pid in by_id ]

        if not selected:
            log_message(
                LG.LLM,
                f"⚠️ هیچ‌یک از product_ids منتخب LLM در محصولات نهایی یافت نشد ({allowed_ids}) | بازگشت به همهٔ کاندیداها",
                LogLevel.WARNING,
            )
            return final_products

        log_message( LG.LLM, f"🎯 محصولات منتخب LLM برای نمایش: {[p.product_id for p in selected]}", LogLevel.DEBUG )
        return selected

    def _build_final_response(
        self,
        req_id: str,
        session_id: str,
        extract_out: LLMExtractSchema,
        effective_filters: MetadataFilters,
        candidates: list[ QdrantProductPayload ],
        final_products: list[ QdrantProductPayload ],
        llm_out: dict,
        t0: float,
    ) -> SearchResponse:
        """‫ساخت SearchResponse نهایی از خروجی تمام مراحل پایپلاین"""
        fallback_steps: int = self._retriever._last_fallback_steps

        # 🎯 منبع حقیقت برای نمایش = انتخاب نهایی LLM (product_ids)
        # ‫LLM از بین محصولات reranked فقط مواردِ منطبق با نیاز کاربر را انتخاب می‌کند؛
        # ‫بنابراین results باید دقیقاً همان‌ها باشد، نه همهٔ کاندیداها.
        selected_products = self._select_llm_products( final_products, llm_out )

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
            ) for p in selected_products
        ]
        return SearchResponse(
            status="partial" if fallback_steps > 0 else "success",
            request_id=req_id,
            session_id=session_id,
            intent=extract_out.intent.value,
            semantic_query=extract_out.semantic_query,
            applied_filters=effective_filters,
            results=results,
            message=str( llm_out.get( "explanation", "" ) ),
            llm_explanation=str( llm_out.get( "explanation", "" ) ),
            next_suggestion=str( llm_out.get( "next_suggestion", "" ) ),
            meta={
                "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ),
                "fallback_steps": fallback_steps,
                "total_candidates": len( candidates ),
                **( llm_out.get( "meta", {} ) ),          # ✅ ادغام ایمن token_usage
            },
        )

    def _build_greeting( self, *, req_id: str, session_id: str, intent: str, query: str, t0: float ) -> SearchResponse:
        """‫ساخت پاسخ احوال‌پرسی سریع (بدون LLM)"""
        fallback_greetings = [ "سلام! چطور می‌تونم کمکتون کنم؟", "درود، چه کمکی از دستم برمیاد؟", "سلام، در خدمتم!" ]
        return SearchResponse(
            status="success",
            request_id=req_id,
            session_id=session_id,
            intent=intent,
            semantic_query=query,
            applied_filters={},
            results=[],
            message=random.choice( fallback_greetings ),
            llm_explanation="",
            next_suggestion="نیازتان را بنویسید.",
            meta={ "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ) },
        )

    @staticmethod
    def _build_empty( *, req_id: str, session_id: str, extract_out: LLMExtractSchema, t0: float ) -> SearchResponse:
        """‫ساخت پاسخ خالی (صفر نتیجه)"""
        return SearchResponse(
            status="empty",
            request_id=req_id,
            session_id=session_id,
            intent=extract_out.intent.value,
            semantic_query=extract_out.semantic_query,
            applied_filters=extract_out.metadata_filters or {},
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

    def _build_clarification( self, *, req_id: str, session_id: str, query: str, question: str | None, t0: float ) -> SearchResponse:
        """‫ساخت پاسخ شفاف‌سازی (Clarification)"""
        clarification_msg = question or "لطفاً جزئیات بیشتری از نیاز خود بفرمایید."
        log_message( LG.LLM, f"❓ Clarification Question: {clarification_msg}", LogLevel.DEBUG )

        return SearchResponse(
            status="clarification",
            request_id=req_id,
            session_id=session_id,
            intent=IntentType.SEARCH.value,
            semantic_query=query,
            applied_filters={},
            results=[],
            message=clarification_msg,
            llm_explanation="",
            next_suggestion="برند، بودجه یا ویژگی خاصی مد نظر دارید؟",
            meta={ "latency_ms": round( ( time.perf_counter() - t0 ) * 1000, 1 ) },
        )
