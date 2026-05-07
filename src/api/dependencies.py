#───────────────────── Imports ─────────────────────
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import HTTPException, Request, status

#───────────────────── Local Imports ─────────────────────
if TYPE_CHECKING:
    from src.core.vector.qdrant_retriever import QdrantHybridRetriever
    from src.services.reranker_service import RerankerService
    from src.core.llm.orchestrator import LLMOrchestrator
    from src.data.repositories.product_repository import ProductRepository


def get_retriever( request: Request ) -> QdrantHybridRetriever:
    """‫تزریق بازیاب ترکیبی از app.state"""
    if not hasattr( request.app.state, "retriever" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس بازیابی در حال راه‌اندازی است" )
    return request.app.state.retriever


def get_reranker( request: Request ) -> RerankerService:
    """‫تزریق سرویس مرتب‌سازی نهایی از app.state"""
    if not hasattr( request.app.state, "reranker" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس رتبه‌بندی در حال راه‌اندازی است" )
    return request.app.state.reranker


def get_llm( request: Request ) -> LLMOrchestrator:
    """‫تزریق اورکستراتور LLM از app.state"""
    if not hasattr( request.app.state, "llm" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس LLM در حال راه‌اندازی است" )
    return request.app.state.llm


def get_product_repo( request: Request ) -> ProductRepository:
    """ ‫تزریق ریپازیتوری محصول از app.state"""
    if not hasattr( request.app.state, "product_repo" ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="سرویس دیتابیس محصول در حال راه‌اندازی است",
        )
    return request.app.state.product_repo
