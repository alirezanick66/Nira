"""‫مدل‌های دادهٔ ورودی و خروجی API
‫مسئول: تعریف ساختارهای اعتبارسنجی‌شده برای درخواست، پاسخ و رویدادهای پایپلاین
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict


class SearchRequest( BaseModel ):
    query: str = Field(..., min_length=1, description="متن جستجوی کاربر" )
    store_id: str = Field( default="default_store", description="شناسه فروشگاه" )
    user_id: str | None = Field( default=None, description="شناسه کاربر سمت فروشگاه" )
    client_session_id: str | None = Field( default=None, description="شناسه نشست کلاینت" )
    domain: str | None = Field( default="mobile", description="دسته‌بندی محصول" )
    top_k: int = Field( default=3, ge=1, le=10, description="تعداد نتایج پیشنهادی" )

    model_config = ConfigDict( json_schema_extra={ "example": { "query": "گوشی گیمینگ زیر ۳۰ میلیون", "store_id": "store_1" } } )


class ErrorLog( BaseModel ):
    """‫ساختار ثبت خطاهای فرانت‌اند (JS/CSS)"""
    message: str
    source: str
    lineno: int
