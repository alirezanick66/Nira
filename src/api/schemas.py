"""‫مدل‌های دادهٔ ورودی و خروجی API
‫مسئول: تعریف ساختارهای اعتبارسنجی‌شده برای درخواست، پاسخ و رویدادهای پایپلاین
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest( BaseModel ):
    query: str = Field(..., min_length=1, description="متن جستجوی کاربر" )
    store_id: str = Field( default="default_store", description="شناسه فروشگاه" )
    user_id: Optional[ str ] = Field( default=None, description="شناسه کاربر در سمت فروشگاه" )
    client_session_id: Optional[ str ] = Field( default=None, description="شناسه نشست سمت کلاینت فروشگاه" )
    domain: Optional[ str ] = Field( default="mobile", description="دسته‌بندی محصول (مثلاً mobile, headphone)" )
    top_k: int = Field( default=3, ge=1, le=10, description="تعداد نتایج پیشنهادی" )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "گوشی گیمینگ زیر ۳۰ میلیون",
                "store_id": "digikala_mobile",
                "user_id": "user_123",
                "domain": "mobile",
            }
        }


class ErrorLog( BaseModel ):
    message: str
    source: str
    lineno: int
