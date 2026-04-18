"""‫مدیریت تزریق وابستگی‌ها (Dependency Injection)
‫مسئول: فراهم‌سازی نمونه‌های سطح‌اپلیکیشن سرویس‌ها به Routeهای FastAPI
"""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from src.config.logging_config import log_message, LogLevel, LG


def get_nlu_pipeline( request: Request ):
    """‫تزریق خط لوله NLU از app.state"""
    return request.app.state.nlu


def get_retriever( request: Request ):
    """‫تزریق بازیاب ترکیبی از app.state"""
    if not hasattr( request.app.state, "retriever" ):
        log_message( LG.API, "⚠️ سرویس Retriever مقداردهی نشده است", LogLevel.WARNING )
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس بازیابی در حال راه‌اندازی است" )
    return request.app.state.retriever


def get_reranker( request: Request ):
    """‫تزریق سرویس مرتب‌سازی نهایی از app.state"""
    if not hasattr( request.app.state, "reranker" ):
        log_message( LG.API, "⚠️ سرویس Reranker مقداردهی نشده است", LogLevel.WARNING )
        raise HTTPException( status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="سرویس رتبه‌بندی در حال راه‌اندازی است" )
    return request.app.state.reranker
