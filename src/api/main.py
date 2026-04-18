"""‫نقطهٔ ورود وب‌سرور FastAPI
‫مسئول: مدیریت چرخه عمر اپلیکیشن، تعریف Routeها، و اجرای هماهنگ پایپلاین NLU → Retrieval → Rerank → LLM
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, status
from contextlib import asynccontextmanager

from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.nlu_pipeline import nlu_pipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator


@asynccontextmanager
async def lifespan( app: FastAPI ) -> AsyncGenerator[ None, None ]:
    """‫مدیریت راه‌اندازی و خاموشی سرویس‌های سنگین (Lifespan Context)"""
    log_message( LG.API, "🚀 در حال بارگذاری سرویس‌های پایه...", LogLevel.INFO )

    # بارگذاری Singletonها در حافظهٔ اپلیکیشن (یک‌بار در طول حیات سرویس)
    app.state.nlu = nlu_pipeline
    app.state.retriever = QdrantHybridRetriever()
    app.state.reranker = RerankerService.get_instance()
    app.state.llm = LLMOrchestrator()

    log_message( LG.API, "✅ سرویس‌ها آمادهٔ پذیرش درخواست هستند", LogLevel.INFO )
    yield

    log_message( LG.API, "🛑 پایان چرخه عمر سرویس‌ها و آزادسازی منابع", LogLevel.INFO )


app = FastAPI(
    title="Nira AI Shopping Assistant",
    description="دستیار هوشمند خرید موبایل مبتنی بر جستجوی ترکیبی، درک زبان طبیعی و تولید پاسخ ساختاریافته",
    version="1.0.0-MVP",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.post( "/api/v1/search", response_model=SearchResponse, status_code=status.HTTP_200_OK )
async def search_products( request: SearchRequest ) -> SearchResponse:
    """‫پردازش کوئری کاربر و بازگرداندن محصولات پیشنهادی + توضیح LLM

    Args:
        request: دادهٔ ورودی شامل متن کوئری، تعداد نتایج و شناسه نشست

    Returns:
        ساختار پاسخ استاندارد شامل نیت، فیلترها، نتایج و توضیحات LLM
    """
    session_id = request.session_id or str( uuid.uuid4() )

    try:
        # 🔹 گام ۱: درک زبان طبیعی (NLU)
        nlu_out = app.state.nlu.process( request.query )

        if nlu_out.is_greeting:
            return SearchResponse( intent="greeting",
                                   semantic_query=request.query,
                                   applied_filters={},
                                   results=[],
                                   message="سلام! چطور می‌تونم در انتخاب گوشی مناسب کمکتون کنم؟",
                                   llm_explanation="پاسخ خوشامدگویی سیستم",
                                   next_suggestion="نیازهای خود را به زبان محاوره‌ای بنویسید." )

        # 🔹 گام ۲: بازیابی ترکیبی (Dense + Sparse + RRF + Metadata Filter)
        candidates = app.state.retriever.search(
            query=nlu_out.semantic_query,
            filters=nlu_out.metadata_filters,
            top_k=max( request.top_k * 2, 10 )          # کاندیدای بیشتر برای دقت Reranker
        )

        if not candidates:
            return SearchResponse( intent=nlu_out.intent,
                                   semantic_query=nlu_out.semantic_query,
                                   applied_filters=nlu_out.metadata_filters,
                                   results=[],
                                   message="متأسفانه محصولی با این مشخصات پیدا نشد. پیشنهاد می‌کنم فیلترها را کمی گسترده‌تر کنید.",
                                   llm_explanation="هیچ تطابقی در پایگاه داده یافت نشد.",
                                   next_suggestion="برند یا رنج قیمت را تغییر دهید." )

        # 🔹 گام ۳: مرتب‌سازی نهایی (Cross-Encoder Reranker)
        final_products = app.state.reranker.rerank(
            query=request.query,          # متن کامل برای درک بهتر Context
            payloads=candidates,
            top_k=request.top_k )

        # 🔹 گام ۴: تولید پاسخ هوشمند (LLM Orchestrator + Memory)
        llm_out = app.state.llm.generate(
            session_id=session_id,
            user_query=request.query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
        )

        # 🔹 گام ۵: نگاشت به مدل پاسخ استاندارد
        results = [
            SearchResultItem(
                product_id=p.product_id,
                title=p.title,
                price=p.price,
                price_range=p.price_range or "نامشخص",
                camera_quality=p.camera_quality or "نامشخص",
                tags=p.tags or [],
                relevance_score=0.0          # رزرو برای فاز Post-MVP
            ) for p in final_products
        ]

        return SearchResponse( intent=nlu_out.intent,
                               semantic_query=nlu_out.semantic_query,
                               applied_filters=nlu_out.metadata_filters,
                               results=results,
                               message=llm_out.get( "explanation", "نتایج بر اساس نیاز شما مرتب شدند." ),
                               llm_explanation=llm_out.get( "explanation", "" ),
                               next_suggestion=llm_out.get( "next_suggestion", "می‌توانید فیلترها را دقیق‌تر کنید." ) )

    except HTTPException:
        raise          # خطاهای اعتبارسنجی/سرویس مستقیم به کلاینت برگردند
    except Exception as exc:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در Endpoint جستجو: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطای داخلی سرور. لطفاً مجدداً تلاش کنید." )
