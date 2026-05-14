"""‫نقطهٔ ورود وب‌سرور FastAPI
‫مسئول: مدیریت چرخه عمر اپلیکیشن، تعریف Routeها، و اجرای هماهنگ پایپلاین NLU → Retrieval → Rerank → LLM
"""
#─────────────────────imports─────────────────────
from __future__ import annotations
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.responses import JSONResponse

#─────────────────────local imports─────────────────────
from services.search_service import SearchService
from src.data.repositories.product_repository import ProductRepository
from src.config.domain_loader import DomainConfigLoader
from src.api.schemas import ErrorLog
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator
from src.config.settings import get_settings
from src.api.routes.search import router as search_router
from src.api.middleware.api_key_middleware import ApiKeyMiddleware
from src.services.embedding_service import EmbeddingService
from src.data.db.engine import DatabaseEngine


@asynccontextmanager
async def lifespan( app: FastAPI ) -> AsyncGenerator[ None, None ]:
    """‫مدیریت راه‌اندازی و خاموشی سرویس‌های سنگین (Lifespan Context)"""

    log_message( LG.API, "🚀 در حال بارگذاری سرویس‌های پایه...", LogLevel.INFO )

    loader = DomainConfigLoader()
    domain = "mobile"
    config = loader.load( domain )

    embedder = EmbeddingService()
    db_engine = DatabaseEngine()

    app.state.db_engine = db_engine
    app.state.product_repo = ProductRepository( db_engine=db_engine )
    app.state.retriever = QdrantHybridRetriever( config, embedding_service=embedder )
    app.state.reranker = RerankerService()
    app.state.llm = LLMOrchestrator( config )
    app.state.search_service = SearchService(
        retriever=app.state.retriever,
        reranker=app.state.reranker,
        llm=app.state.llm,
        image_repo=app.state.product_repo,
    )

    log_message( LG.API, "✅ سرویس‌ها آمادهٔ پذیرش درخواست هستند", LogLevel.INFO )
    yield
    log_message( LG.API, "🛑 پایان چرخه عمر سرویس‌ها و آزادسازی منابع", LogLevel.INFO )


app = FastAPI(
    title=get_settings().APP_NAME,
    description="دستیار هوشمند خرید موبایل مبتنی بر جستجوی ترکیبی، درک زبان طبیعی و تولید پاسخ ساختاریافته",
    version="1.0.0",
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

app.add_middleware(
    ApiKeyMiddleware,
    api_key=get_settings().API_KEY_STORE_MAP,
)

app.include_router( search_router )


@app.post( "/api/log-error" )
async def log_error( error: ErrorLog ):
    #چاپ خطاهای جاوا اسکریپت
    log_message( LG.API, f"{error.message} at {error.source}:{error.lineno}" )


@app.exception_handler( HTTPException )
async def custom_http_exception( request, exc ):
    return JSONResponse( status_code=exc.status_code,
                         content={
                             "status": "error",
                             "request_id": getattr( request.state, "req_id", "" ),
                             "detail": exc.detail
                         } )


FRONTEND_DIR = Path( __file__ ).resolve().parents[ 2 ] / "frontend"
if FRONTEND_DIR.exists():
    app.mount( "/", StaticFiles( directory=str( FRONTEND_DIR ), html=True ), name="frontend" )
