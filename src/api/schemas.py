"""‫مدل‌های دادهٔ ورودی و خروجی API
‫مسئول: تعریف ساختارهای اعتبارسنجی‌شده برای درخواست و پاسخ جستجوی محصول
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest( BaseModel ):
    query: str = Field(..., min_length=1, description="متن جستجوی کاربر" )

    # --- فیلدهای B2B (اختیاری برای تست مستقیم، اجباری برای فروشگاه) ---
    store_id: str = Field( default="default_store", description="شناسه فروشگاه" )
    user_id: Optional[ str ] = Field( default=None, description="شناسه کاربر در سمت فروشگاه" )
    client_session_id: Optional[ str ] = Field( default=None, description="شناسه نشست سمت کلاینت فروشگاه" )

    # --- تنظیمات پیشرفته (اختیاری) ---
    domain: Optional[ str ] = Field( default="mobile", description="دسته‌بندی محصول (مثلاً mobile, headphone)" )
    top_k: int = Field( default=3, ge=1, le=10, description="تعداد نتایج پیشنهادی" )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "گوشی گیمینگ زیر ۳۰ میلیون",
                "store_id": "digikala_mobile",
                "user_id": "user_123",
                "domain": "mobile"
            }
        }


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
