"""‫مدیریت تزریق وابستگی‌ها (Dependency Injection)
‫مسئول: فراهم‌سازی نمونه‌های سطح‌اپلیکیشن سرویس‌ها به Routeهای FastAPI
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from src.core.nlu.nlu_pipeline import NLUPipeline
    from src.core.vector.qdrant_retriever import QdrantHybridRetriever
    from src.services.reranker_service import RerankerService


def get_nlu_pipeline( request: Request ) -> "NLUPipeline":
    """‫تزریق خط لوله NLU از app.state"""
    if not hasattr( request.app.state, "nlu" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس NLU در حال راه‌اندازی است" )
    return request.app.state.nlu


def get_retriever( request: Request ) -> "QdrantHybridRetriever":
    """‫تزریق بازیاب ترکیبی از app.state"""
    if not hasattr( request.app.state, "retriever" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس بازیابی در حال راه‌اندازی است" )
    return request.app.state.retriever


def get_reranker( request: Request ) -> "RerankerService":
    """‫تزریق سرویس مرتب‌سازی نهایی از app.state"""
    if not hasattr( request.app.state, "reranker" ):
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس رتبه‌بندی در حال راه‌اندازی است" )
    return request.app.state.reranker
