"""‫سرویس مشترک پایپلاین جستجو (Search Pipeline Service)

‫مسئول: اجرای کامل زنجیره NLU → Retrieval → Rerank → LLM و بازگشت پاسخ نهایی.
‫این ماژول هیچ وابستگی به پروتکل HTTP، SSE یا JSON ندارد و کاملاً Domain-Pure است.
"""
#─────────────────────imports─────────────────────
from __future__ import annotations
import asyncio
import time
import uuid
import logging
from dataclasses import dataclass
from typing import AsyncIterator
import random

#─────────────────────local imports─────────────────────
from src.api.schemas import SearchResponse, SearchResultItem
from src.core.llm.orchestrator import LLMOrchestrator
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.nlu.schemas import NLUFilterQuery
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.data.repositories.product_repository import ProductRepository
from src.config.logging_config import log_message, LogLevel, LG

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
        image_repo: ProductRepository | None = None,
    ) -> None:
        self._nlu = nlu
        self._retriever = retriever
        self._reranker = reranker
        self._llm = llm
        self._image_repo = image_repo

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
            yield self._build_greeting( req_id=req_id, session_id=session_id, query=query, t0=t0, config=self._nlu._config )
            return

        # ── ادغام فیلترهای refine با session قبلی ────────────────────────────
        effective_filters = await self._merge_refine_filters(
            intent=nlu_out.intent,
            new_filters=dict( nlu_out.metadata_filters ),
            session_id=session_id,
        )
        if nlu_out.sort_directive and nlu_out.sort_directive.get( "key" ) == "price" and "price" in effective_filters:
            del effective_filters[ "price" ]
            log_message( LG.LLM, "🧹 حذف فیلتر عددی price به دلیل فعال‌بودن sort_directive مقایسه‌ای", LogLevel.DEBUG )
        log_message( LG.LLM, f"🔀 فیلترهای مؤثر | Intent: {nlu_out.intent} | Filters: {effective_filters}", LogLevel.DEBUG )

        # ── مرحله ۲: جستجو ───────────────────────────────────────────────────
        yield PipelineStatus( step="searching", message=self._STEP_MESSAGES[ "searching" ] )
        # ‫ اصلاح کوئری معنایی برای Refine‌های مقایسه‌ای
        retrieve_query = nlu_out.semantic_query
        if nlu_out.intent == "refine" and len( retrieve_query.replace( " ", "" ) ) < 4:
            retrieve_query = "گوشی موبایل جدید"
            log_message( LG.LLM, "🌱 کوئری refine کوتاه بود → تزریق Seed دامنه برای بازیابی صحیح کاندیداها", LogLevel.DEBUG )

        candidates = await asyncio.to_thread(
            self._retriever.search,
            query=retrieve_query,          # ← استفاده از کوئری اصلاح‌شده
            filters=effective_filters,
            top_k=max( top_k * 2, 10 ),
        )

        fallback_steps: int = getattr( self._retriever, "_last_fallback_steps", 0 )

        # ── مدیریت هوشمند Fallback برای فیلترهای عددی (Closest Available) ──
        if fallback_steps > 0 and candidates:
            # بررسی فیلترهای عددی که احتمالاً در Fallback حذف شده‌اند
            for field, constraint in effective_filters.items():
                if isinstance( constraint, dict ):
                    op, target = next( iter( constraint.items() ) )
                    # آیا هیچ نتیجه‌ای شرط عددی را برآورده می‌کند？
                    has_match = False
                    for c in candidates:
                        val = getattr( c, field, None )
                        if val is not None:
                            if (op == ">=" and val >= target) or (op == "<=" and val <= target) or \
                            (op == ">" and val > target) or (op == "<" and val < target):
                                has_match = True
                                break

                    if not has_match:
                        # مرتب‌سازی بر اساس جهت فیلتر برای یافتن نزدیک‌ترین گزینه موجود
                        reverse = op in ( ">=", ">" )
                        candidates.sort( key=lambda p: getattr( p, field, 0 ) or 0, reverse=reverse )
                        log_message(
                            LG.RETRIEVAL,
                            f"🎯 نزدیک‌ترین گزینه موجود انتخاب شد | {field} {op} {target} → بهترین: {getattr(candidates[0], field, 'N/A')}",
                            LogLevel.INFO )
                        break          # فقط یک فیلتر عددیِ غالب را مدیریت می‌کنیم
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
        # ‫ Post-Retrieval Enrichment: واکشی image_url از PG
        if self._image_repo and final_products:
            ids = [ p.product_id for p in final_products ]
            url_map = await self._image_repo.batch_get_image_urls( ids )
            for p in final_products:
                if hasattr( p, "image_url" ):
                    p.image_url = url_map.get( p.product_id )

            #  لاگ محصولات نهایی (نام و قیمت)
        if final_products:
            summary = [ f"{p.title[:40].replace('\n', ' ')}... | {p.price:,.0f} تومان" for p in final_products[ :2 ] ]
            log_message( LG.LLM, f"{summary}", LogLevel.DEBUG )

        # ── مرحله ۴: تولید پاسخ LLM ─────────────────────────────────────────
        yield PipelineStatus( step="generating", message=self._STEP_MESSAGES[ "generating" ] )

        llm_out: dict = await self._llm.generate(
            session_id=session_id,
            user_query=query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
            applied_filters=effective_filters,          # ✅ ذخیره در حافظه
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
            applied_filters=effective_filters,
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
    def _build_greeting( *, req_id: str, session_id: str, query: str, t0: float, config: dict | None = None ) -> SearchResponse:
        """‫ساخت پاسخ احوال‌پرسی"""

        greeting_cfg = config.get( "intent_keywords", {} ).get( "greeting", {} ) if config else {}
        responses = greeting_cfg.get( "greeting_responses", "" )
        selected = random.choice( responses )

        return SearchResponse(
            status="success",
            request_id=req_id,
            session_id=session_id,
            intent="greeting",
            semantic_query=query,
            applied_filters={},
            results=[],
            message=selected,
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

    async def _merge_refine_filters(
        self,
        intent: str,
        new_filters: dict,
        session_id: str,
    ) -> dict:
        """فیلترهای جدید را با فیلترهای session قبلی ادغام می‌کند.
 
        منطق ادغام:
        - ‫اگر intent برابر refine نبود → فیلترهای جدید بدون تغییر برگشت می‌دهد
        - ‫اگر intent برابر refine بود:
           ‫ ۱. فیلترهای session قبلی به‌عنوان پایه استفاده می‌شوند
           ‫ ۲. فیلترهای جدید (مثل قیمت جدید) روی فیلترهای قبلی override می‌کنند
            ‫۳. فیلترهایی مثل brand که در کوئری جدید نیستند، حفظ می‌شوند
 
        Args:
            intent: نیت تشخیص‌داده‌شده توسط NLU
            new_filters: فیلترهای استخراج‌شده از کوئری جدید
            session_id: شناسه نشست برای دسترسی به حافظه
 
        Returns:
            دیکشنری فیلترهای ادغام‌شده
        """
        if intent != "refine":
            return new_filters

        last_filters = await self._llm._memory.get_last_filters( session_id )

        if not last_filters:
            log_message( LG.LLM, "⚠️ refine: فیلتر قبلی در حافظه یافت نشد، فیلترهای جدید استفاده می‌شوند", LogLevel.WARNING )
            return new_filters

        # پایه: فیلترهای session قبلی
        merged = dict( last_filters )

        # ‫override: فیلترهای جدید (مثل قیمت جدیدتر) جایگزین می‌شوند
        merged.update( new_filters )

        log_message( LG.LLM, f"🔀 refine merge | قبلی: {last_filters} | جدید: {new_filters} | نهایی: {merged}", LogLevel.DEBUG )
        return merged
