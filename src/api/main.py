"""‫نقطهٔ ورود وب‌سرور FastAPI
‫مسئول: مدیریت چرخه عمر اپلیکیشن، تعریف Routeها، و اجرای هماهنگ پایپلاین
"""
from __future__ import annotations

from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, status
from contextlib import asynccontextmanager

from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from src.api.dependencies import get_nlu_pipeline, get_retriever, get_reranker
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.nlu_pipeline import nlu_pipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService


@asynccontextmanager
async def lifespan( app: FastAPI ) -> AsyncGenerator[ None, None ]:
    """‫مدیریت راه‌اندازی و خاموشی سرویس‌های سنگین (Lifespan Context)"""
    log_message( LG.API, "🚀 در حال بارگذاری سرویس‌های پایه...", LogLevel.INFO )

    # بارگذاری Singletonها در حافظهٔ اپلیکیشن
    app.state.nlu = nlu_pipeline
    app.state.retriever = QdrantHybridRetriever()
    app.state.reranker = RerankerService.get_instance()

    log_message( LG.API, "✅ سرویس‌ها آمادهٔ پذیرش درخواست هستند", LogLevel.INFO )
    yield

    log_message( LG.API, "🛑 پایان چرخه عمر سرویس‌ها", LogLevel.INFO )


app = FastAPI(
    title="Nira AI Shopping Assistant",
    description="دستیار هوشمند خرید موبایل مبتنی بر جستجوی ترکیبی و درک زبان طبیعی",
    version="1.0.0-MVP",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.post( "/api/v1/search", response_model=SearchResponse, status_code=status.HTTP_200_OK )
async def search_products(
        request: SearchRequest,
        nlu=Depends( get_nlu_pipeline ),
        retriever=Depends( get_retriever ),
        reranker=Depends( get_reranker ),
) -> SearchResponse:
    """‫پردازش کوئری کاربر و بازگرداندن محصولات پیشنهادی
    Args:
        request: دادهٔ ورودی شامل متن کوئری و تعداد نتایج
        nlu: خط لوله درک زبان طبیعی
        retriever: سرویس بازیابی ترکیبی
        reranker: سرویس مرتب‌سازی نهایی
    Returns:
        ساختار پاسخ استاندارد شامل نیت، فیلترها و لیست محصولات
    """
    try:
        # ‫گام ۱: پردازش NLU
        nlu_out = nlu.process( request.query )

        if nlu_out.is_greeting:
            return SearchResponse( intent="greeting",
                                   semantic_query=request.query,
                                   applied_filters={},
                                   results=[],
                                   message="سلام! چطور می‌تونم در انتخاب گوشی مناسب کمکتون کنم؟" )

        # ‫گام ۲: بازیابی ترکیبی (Dense + Sparse + RRF + Metadata)
        candidates = retriever.search(
            query=nlu_out.semantic_query,
            filters=nlu_out.metadata_filters,
            top_k=request.top_k * 2          # ‫دریافت کاندیدای بیشتر برای دقت Reranker
        )

        if not candidates:
            return SearchResponse( intent=nlu_out.intent,
                                   semantic_query=nlu_out.semantic_query,
                                   applied_filters=nlu_out.metadata_filters,
                                   results=[],
                                   message="متأسفانه محصولی با این مشخصات پیدا نشد. پیشنهاد می‌کنم فیلترها را کمی گسترده‌تر کنید." )

        # ‫گام ۳: مرتب‌سازی نهایی (Cross-Encoder Reranker)
        final_products = reranker.rerank(
            query=request.query,          # ‫استفاده از متن کامل برای درک Context
            payloads=candidates,
            top_k=request.top_k )

        # ‫نگاشت به مدل پاسخ استاندارد
        results = [
            SearchResultItem(
                product_id=p.product_id,
                title=p.title,
                price=p.price,
                price_range=p.price_range or "نامشخص",
                camera_quality=p.camera_quality or "نامشخص",
                tags=p.tags or [],
                relevance_score=0.0          # ‫رزرو برای فاز Post-MVP
            ) for p in final_products
        ]

        return SearchResponse( intent=nlu_out.intent,
                               semantic_query=nlu_out.semantic_query,
                               applied_filters=nlu_out.metadata_filters,
                               results=results,
                               message="✅ نتایج بر اساس نیاز شما مرتب‌سازی شدند." )

    except HTTPException:
        raise          # ‫خطاهای اعتبارسنجی/سرویس مستقیم به کلاینت برگردند
    except Exception as exc:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در Endpoint جستجو: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطای داخلی سرور. لطفاً مجدداً تلاش کنید." )
