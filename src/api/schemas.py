"""‫مدل‌های دادهٔ ورودی و خروجی API
‫مسئول: تعریف ساختارهای اعتبارسنجی‌شده برای درخواست و پاسخ جستجوی محصول
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest( BaseModel ):
    """‫ساختار درخواست جستجو از کلاینت"""
    query: str = Field( min_length=1, max_length=200, description="متن کوئری کاربر به زبان طبیعی (فارسی/انگلیسی)" )
    top_k: int = Field( default=5, ge=1, le=10, description="تعداد نتایج نهایی مورد نیاز" )
    session_id: str | None = Field( default=None, description="شناسه نشست برای حفظ حافظه مکالمه" )


class SearchResultItem( BaseModel ):
    """‫ساختار هر محصول در پاسخ نهایی"""
    product_id: int
    title: str
    price: int
    price_range: str
    camera_quality: str
    tags: list[ str ] = []
    image_url: str | None = Field( default=None, description="لینک تصویر محصول" )
    relevance_score: float = Field( default=0.0, description=" ‫امتیاز تطبیق پس از Reranking" )


class SearchResponse( BaseModel ):
    """ ‫ساختار پاسخ استاندارد API نسخه B2B"""
    status: str = Field( description="وضعیت پاسخ: success | partial (با fallback) | empty | error" )
    request_id: str = Field( description="شناسه یکتای درخواست برای ردیابی و دیباگ" )
    session_id: str = Field( description="شناسه نشست فعال (برای ارسال در درخواست‌های بعدی جهت refine)" )

    intent: str = Field( description="نیت تشخیص‌داده‌شده توسط NLU" )
    semantic_query: str = Field( description="متن پاک‌شدهٔ ارسالی به موتور جستجو" )
    applied_filters: dict = Field( description="فیلترهای متادیتا اعمال‌شده در Qdrant" )

    results: list[ SearchResultItem ]
    message: str = Field( description="پیام سیستمی یا راهنما برای کاربر نهایی" )
    llm_explanation: str = Field( description="توضیح تولیدشده توسط LLM" )
    next_suggestion: str = Field( description="پیشنهاد اقدام بعدی یا فیلتر جدید" )

    meta: dict[ str, object ] | None = Field(
        default=None, description="اطلاعات اجرایی: latency_ms, fallback_steps, warnings, reranker_score_range" )


class ErrorLog( BaseModel ):
    message: str
    source: str
    lineno: int
