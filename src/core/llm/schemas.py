"""‫مدل‌های Pydantic برای اعتبارسنجی خروجی ساختاریافته LLM
‫مسئول: تعریف اسکیماهای دقیق JSON که مدل موظف به تولید آن‌هاست
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class LLMResponseSchema( BaseModel ):
    """‫ساختار استاندارد پاسخ LLM برای دستیار خرید
    ‫تمامی فیلدها اجباری هستند تا از تولید JSON ناقص جلوگیری شود
    """
    product_ids: list[ int ] = Field( description="لیست شناسه محصولات پیشنهادی (حداکثر 2 عدد)" )
    explanation: str = Field( description="توضیح شفاف، دوستانه و مبتنی بر نیاز کاربر درباره دلیل پیشنهاد" )
    next_suggestion: str = Field( description="پیشنهاد اقدام بعدی یا فیلتر جدید در صورت عدم رضایت" )
