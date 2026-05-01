"""روتر اختصاصی جستجوی محصولات (نسخه B2B استاندارد)"""
#───────────────────── Imports ─────────────────────
import uuid
import time
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

#───────────────────── Local Imports ─────────────────────
from src.api.schemas import SearchRequest, SearchResponse, SearchResultItem
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.core.llm.orchestrator import LLMOrchestrator
from src.api.dependencies import get_nlu_pipeline, get_retriever, get_reranker, get_llm
from src.config.logging_config import log_message, LogLevel, LG

router = APIRouter( prefix="/api/v1", tags=[ "Search" ] )


@router.post( "/search", response_model=SearchResponse, status_code=status.HTTP_200_OK )
async def search_products(
        request: SearchRequest,
        nlu: NLUPipeline = Depends( get_nlu_pipeline ),
        retriever: QdrantHybridRetriever = Depends( get_retriever ),
        reranker: RerankerService = Depends( get_reranker ),
        llm: LLMOrchestrator = Depends( get_llm ),
) -> SearchResponse:
    """پردازش کوئری کاربر و بازگرداندن پاسخ استاندارد ساختاریافته"""
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
                                   next_suggestion="نیازتان را بنویسید.",
                                   meta={ "latency_ms": 0.0 } )

        candidates = await asyncio.to_thread( retriever.search,
                                              query=nlu_out.semantic_query,
                                              filters=nlu_out.metadata_filters,
                                              top_k=max( request.top_k * 2, 10 ) )
        if not candidates:
            latency = round( ( time.perf_counter() - t0 ) * 1000, 1 )
            return SearchResponse( status="empty",
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
                                       "total_candidates": 0,
                                   } )
        fallback_steps = getattr( retriever, "_last_fallback_steps", 0 )
        response_status = "partial" if fallback_steps > 0 else "success"

        final_products = await asyncio.to_thread( reranker.rerank, query=request.query, payloads=candidates, top_k=request.top_k )

        llm_out = await llm.generate(
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
                              image_url=p.image_url,
                              relevance_score=getattr( p, "rerank_score", 0.0 ) ) for p in final_products
        ]

        latency_ms = round( ( time.perf_counter() - t0 ) * 1000, 1 )
        meta = { "latency_ms": latency_ms, "fallback_steps": fallback_steps, "total_candidates": len( candidates ) }

        return SearchResponse( status=response_status,
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

    except HTTPException:
        raise
    except Exception as exc:
        log_message( LG.API, f"خطای پیش‌بینی‌نشده در Endpoint جستجو: {exc}", LogLevel.ERROR )
        raise HTTPException( status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="خطای داخلی سرور." )
