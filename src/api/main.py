"""‫نقطهٔ ورود وب‌سرور FastAPI
‫مسئول: مدیریت چرخه عمر اپلیکیشن، تعریف Routeها، و اجرای هماهنگ پایپلاین NLU → Retrieval → Rerank → LLM
"""
from __future__ import annotations
import uuid
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, status
from contextlib import asynccontextmanager
from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator
from src.api.dependencies import get_nlu_pipeline, get_retriever, get_reranker


@asynccontextmanager
async def lifespan( app: FastAPI ) -> AsyncGenerator[ None, None ]:
    """‫مدیریت راه‌اندازی و خاموشی سرویس‌های سنگین (Lifespan Context)"""
    log_message( LG.API, "🚀 در حال بارگذاری سرویس‌های پایه...", LogLevel.INFO )
    app.state.nlu = NLUPipeline()
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
async def search_products(
        request: SearchRequest,
        nlu: NLUPipeline = Depends( get_nlu_pipeline ),
        retriever: QdrantHybridRetriever = Depends( get_retriever ),
        reranker: RerankerService = Depends( get_reranker ),
) -> SearchResponse:
    """‫پردازش کوئری کاربر و بازگرداندن محصولات پیشنهادی + توضیح LLM"""
    session_id = request.session_id or str( uuid.uuid4() )

    try:
        nlu_out = nlu.process( request.query )

        if nlu_out.is_greeting:
            return SearchResponse( intent="greeting",
                                   semantic_query=request.query,
                                   applied_filters={},
                                   results=[],
                                   message="سلام! چطور می‌تونم در انتخاب گوشی مناسب کمکتون کنم؟",
                                   llm_explanation="پاسخ خوشامدگویی سیستم",
                                   next_suggestion="نیازهای خود را به زبان محاوره‌ای بنویسید." )

        candidates = retriever.search( query=nlu_out.semantic_query,
                                       filters=nlu_out.metadata_filters,
                                       top_k=max( request.top_k * 2, 10 ) )

        if not candidates:
            return SearchResponse( intent=nlu_out.intent,
                                   semantic_query=nlu_out.semantic_query,
                                   applied_filters=nlu_out.metadata_filters,
                                   results=[],
                                   message="متأسفانه محصولی با این مشخصات پیدا نشد. پیشنهاد می‌کنم فیلترها را کمی گسترده‌تر کنید.",
                                   llm_explanation="هیچ تطابقی در پایگاه داده یافت نشد.",
                                   next_suggestion="برند یا رنج قیمت را تغییر دهید." )

        final_products = reranker.rerank( query=request.query, payloads=candidates, top_k=request.top_k )

        llm_out = app.state.llm.generate(
            session_id=session_id,
            user_query=request.query,
            intent=nlu_out.intent,
            filters_str=str( nlu_out.metadata_filters ),
            products=final_products,
        )

        results = [
            SearchResultItem( product_id=p.product_id,
                              title=p.title,
                              price=p.price,
                              price_range=p.price_range or "نامشخص",
                              camera_quality=p.camera_quality or "نامشخص",
                              tags=p.tags or [],
                              relevance_score=0.0 ) for p in final_products
        ]

        return SearchResponse( intent=nlu_out.intent,
                               semantic_query=nlu_out.semantic_query,
                               applied_filters=nlu_out.metadata_filters,
                               results=results,
                               message=llm_out.get( "explanation", "نتایج بر اساس نیاز شما مرتب شدند." ),
                               llm_explanation=llm_out.get( "explanation", "" ),
                               next_suggestion=llm_out.get( "next_suggestion", "می‌توانید فیلترها را دقیق‌تر کنید." ) )

    except HTTPException:
        raise
    except Exception as exc:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در Endpoint جستجو: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطای داخلی سرور. لطفاً مجدداً تلاش کنید." )
