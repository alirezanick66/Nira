"""‫نقطهٔ ورود وب‌سرور FastAPI
‫مسئول: مدیریت چرخه عمر اپلیکیشن، تعریف Routeها، و اجرای هماهنگ پایپلاین NLU → Retrieval → Rerank → LLM
"""
#─────────────────────imports─────────────────────
from __future__ import annotations
import uuid
import asyncio
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, status
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import time

#─────────────────────local imports─────────────────────
from src.config.domain_loader import DomainConfigLoader
from src.api.schemas import ErrorLog, SearchRequest, SearchResponse, SearchResultItem
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator
from src.api.dependencies import get_nlu_pipeline, get_retriever, get_reranker, get_llm
from src.config.settings import get_settings


@asynccontextmanager
async def lifespan( app: FastAPI ) -> AsyncGenerator[ None, None ]:
    """‫مدیریت راه‌اندازی و خاموشی سرویس‌های سنگین (Lifespan Context)"""

    log_message( LG.API, "🚀 در حال بارگذاری سرویس‌های پایه...", LogLevel.INFO )

    loader = DomainConfigLoader()
    domain = "mobile"
    config = loader.load( domain )

    app.state.nlu = NLUPipeline( domain=domain, config_loader=loader )
    app.state.retriever = QdrantHybridRetriever( config )
    app.state.reranker = RerankerService()
    app.state.llm = LLMOrchestrator( config )

    log_message( LG.API, "✅ سرویس‌ها آمادهٔ پذیرش درخواست هستند", LogLevel.INFO )
    yield
    log_message( LG.API, "🛑 پایان چرخه عمر سرویس‌ها و آزادسازی منابع", LogLevel.INFO )


app = FastAPI(
    title=get_settings().APP_NAME,
    description="دستیار هوشمند خرید موبایل مبتنی بر جستجوی ترکیبی، درک زبان طبیعی و تولید پاسخ ساختاریافته",
    version="1.0.0-MVP",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ "*" ],
    allow_credentials=True,
    allow_methods=[ "*" ],
    allow_headers=[ "*" ],
)


@app.post( "/api/v1/search", response_model=SearchResponse, status_code=status.HTTP_200_OK )
async def search_products(
    request: SearchRequest,
    nlu: NLUPipeline = Depends( get_nlu_pipeline ),
    retriever: QdrantHybridRetriever = Depends( get_retriever ),
    reranker: RerankerService = Depends( get_reranker ),
    llm: LLMOrchestrator = Depends( get_llm )
) -> SearchResponse:
    t0 = time.perf_counter()
    req_id = str( uuid.uuid4() )
    session_id = request.session_id or str( uuid.uuid4() )

    try:
        nlu_out = nlu.process( request.query )

        if nlu_out.is_greeting:
            return SearchResponse( status="success",
                                   request_id=req_id,
                                   session_id=session_id,
                                   intent="greeting",
                                   semantic_query=request.query,
                                   applied_filters={},
                                   results=[],
                                   message="سلام! چطور می‌تونم کمکتون کنم؟",
                                   llm_explanation="",
                                   next_suggestion="نیازتان را بنویسید." )

        candidates = await asyncio.to_thread( retriever.search,
                                              query=nlu_out.semantic_query,
                                              filters=nlu_out.metadata_filters,
                                              top_k=request.top_k * 2 )

        fallback_steps = getattr( retriever, "_last_fallback_steps", 0 )          # نیاز به یک خط لاگ در retriever
        status = "success" if candidates else "empty"
        if fallback_steps > 0: status = "partial"

        final_products = await asyncio.to_thread( reranker.rerank, query=request.query, payloads=candidates, top_k=request.top_k )

        llm_out = await llm.generate( session_id=session_id,
                                      user_query=request.query,
                                      intent=nlu_out.intent,
                                      filters_str=str( nlu_out.metadata_filters ),
                                      products=final_products )

        results = [
            SearchResultItem( product_id=p.product_id,
                              title=p.title,
                              price=p.price,
                              price_range=p.price_range or "نامشخص",
                              camera_quality=p.camera_quality or "نامشخص",
                              tags=p.tags or [],
                              image_url=p.image_url,
                              relevance_score=getattr( p, "rerank_score", 0.0 ) ) for p in final_products
        ]

        latency_ms = round( ( time.perf_counter() - t0 ) * 1000, 1 )
        meta = { "latency_ms": latency_ms, "fallback_steps": fallback_steps, "total_candidates": len( candidates ) }

        return SearchResponse( status=status,
                               request_id=req_id,
                               session_id=session_id,
                               intent=nlu_out.intent,
                               semantic_query=nlu_out.semantic_query,
                               applied_filters=nlu_out.metadata_filters,
                               results=results,
                               message=str( llm_out.get( "explanation", "" ) ),
                               llm_explanation=str( llm_out.get( "explanation", "" ) ),
                               next_suggestion=str( llm_out.get( "next_suggestion", "" ) ),
                               meta=meta )

    except Exception as exc:
        return SearchResponse( status="error",
                               request_id=req_id,
                               session_id=session_id,
                               intent="unknown",
                               semantic_query="",
                               applied_filters={},
                               results=[],
                               message="خطای داخلی سرور.",
                               llm_explanation="",
                               next_suggestion="",
                               meta={ "error": str( exc ) } )


@app.post( "/api/log-error" )
async def log_error( error: ErrorLog ):
    #چاپ خطاهای جاوا اسکریپت
    log_message( LG.API, f"{error.message} at {error.source}:{error.lineno}" )


FRONTEND_DIR = Path( __file__ ).resolve().parents[ 2 ] / "frontend"
if FRONTEND_DIR.exists():
    app.mount( "/", StaticFiles( directory=str( FRONTEND_DIR ), html=True ), name="frontend" )
