"""‫مدل‌های Pydantic برای اعتبارسنجی خروجی ساختاریافته ‫LLM
‫مسئول: تعریف اسکیماهای دقیق JSON که مدل موظف به تولید آن‌هاست (فاز استخراج و پاسخ نهایی)
"""
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import TypeAlias

# ──────────────────────────────────────────────────────────────────────────
# نوع‌های داده‌ای فیلترهای متادیتا (انتقال‌یافته از لایهٔ NLU برای قطع وابستگی)
# ──────────────────────────────────────────────────────────────────────────
NumericFilterValue: TypeAlias = int | float
RangeFilter: TypeAlias = dict[ str, NumericFilterValue ]
ListFilter: TypeAlias = list[ str ]
ScalarFilter: TypeAlias = str | int | float | bool
MetadataFilterValue: TypeAlias = RangeFilter | ListFilter | ScalarFilter
MetadataFilters: TypeAlias = dict[ str, MetadataFilterValue ]


# ──────────────────────────────────────────────────────────────────────────
# تعریف نیت‌های مجاز
# ──────────────────────────────────────────────────────────────────────────
class IntentType( str, Enum ):
    """
    نیت‌های مجاز برای تشخیص توسط مدل زبانی.
    """
    SEARCH = "search"          # جستجوی جدید
    REFINE = "refine"          # فیلتر کردن/تغییر نتایج قبلی
    COMPARE = "compare"          # مقایسه دو یا چند محصول
    GENERAL_CHAT = "general_chat"          # احوال‌پرسی یا سوال نامرتبط


# ──────────────────────────────────────────────────────────────────────────
# اسکیمای استخراج (LLM Call 1)
# ──────────────────────────────────────────────────────────────────────────
class LLMExtractSchema( BaseModel ):
    """
    ساختار خروجی مرحلهٔ اول LLM (استخراج نیت و فیلترها).
    تمام فیلدها اجباری هستند تا از تولید JSON ناقص جلوگیری شود.
    """
    intent: IntentType = Field( description="نیت تشخیص‌داده‌شده" )
    semantic_query: str = Field( description="عبارت بهینه‌شده و تمیز برای جستجوی برداری/کلیدواژه‌ای" )
    metadata_filters: MetadataFilters = Field( default_factory=dict, description="فیلترهای ساختاریافته سازگار با Qdrant" )
    needs_clarification: bool = Field( default=False, description="آیا کوئری مبهم است و نیاز به پرسش تکمیلی دارد؟" )
    clarification_question: str | None = Field( default=None, description="سوال شفاف‌ساز در صورت ابهام کوئری" )
    conflict_reason: str | None = Field( default=None, description="دلیل تشخیص تضاد در فیلترها (در صورت وجود)" )
    has_conflict: bool = Field( default=False, description="آیا تضاد منطقی بین فیلترهای درخواست‌شده وجود دارد؟" )


# ──────────────────────────────────────────────────────────────────────────
# اسکیمای پاسخ نهایی (LLM Call 2 - حفظ‌شده برای سازگاری)
# ──────────────────────────────────────────────────────────────────────────
class LLMResponseSchema( BaseModel ):
    """‫ساختار استاندارد پاسخ LLM برای دستیار خرید
   ‫ تمامی فیلدها اجباری هستند تا از تولید JSON ناقص جلوگیری شود
    """
    product_ids: list[ int ] = Field( description="لیست شناسه محصولات پیشنهادی (حداکثر 2 عدد)" )
    explanation: str = Field( description="توضیح شفاف، دوستانه و مبتنی بر نیاز کاربر درباره دلیل پیشنهاد" )
    next_suggestion: str = Field( description="پیشنهاد اقدام بعدی یا فیلتر جدید در صورت عدم رضایت" )
