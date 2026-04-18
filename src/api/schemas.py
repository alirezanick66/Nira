"""‫مدل‌های دادهٔ ورودی و خروجی API
‫مسئول: تعریف ساختارهای اعتبارسنجی‌شده برای درخواست و پاسخ جستجوی محصول
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest( BaseModel ):
    """‫ساختار درخواست جستجو از کلاینت"""
    query: str = Field( min_length=1, max_length=200, description="متن کوئری کاربر به زبان طبیعی (فارسی/انگلیسی)" )
    top_k: int = Field( default=5, ge=1, le=10, description="تعداد نتایج نهایی مورد نیاز" )


class SearchResultItem( BaseModel ):
    """‫ساختار هر محصول در پاسخ نهایی"""
    product_id: int
    title: str
    price: int
    price_range: str
    camera_quality: str
    tags: list[ str ]
    relevance_score: float = Field( default=0.0, description=" ‫امتیاز تطبیق پس از Reranking (در MVP رزرو)" )


class SearchResponse( BaseModel ):
    """‫ساختار پاسخ استاندارد API"""
    intent: str = Field( description="نیت تشخیص‌داده‌شده توسط NLU" )
    semantic_query: str = Field( description="متن پاک‌شدهٔ ارسالی به موتور جستجو" )
    applied_filters: dict = Field( description="فیلترهای متادیتا اعمال‌شده در Qdrant" )
    results: list[ SearchResultItem ]
    message: str = Field( description="پیام سیستمی یا راهنما برای کاربر" )
