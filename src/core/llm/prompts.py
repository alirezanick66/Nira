"""موتور قالب‌سازی پرامپت‌های محصول‌محور
مسئول: تولید System/User Prompt بر اساس Intent و داده‌های بازیابی‌شده
"""
#─────────────────────  Imports ─────────────────────
from __future__ import annotations
from groq.types.chat import ChatCompletionMessageParam

#───────────────────── Local Imports ─────────────────────
from src.core.vector.qdrant_payload import QdrantProductPayload

# ✅ ‫اصلاح: حذف دستور تکراری JSON (چون در لایه کلاینت به‌صورت ساختاریافته تنظیم شده است)
_SYSTEM_BASE = (
    "تو یک دستیار خرید هوشمند، دقیق و همدل هستی. "
    "تنها از اطلاعات محصولات ارائه‌شده استفاده کن و هرگز اطلاعاتی ساختگی تولید نکن. "
    "پاسخ تو باید **فقط** یک JSON با این ساختار دقیق باشد: "
    '{"product_ids": [int, int], "explanation": "متن", "next_suggestion": "متن"}\n'
    "دستورالعمل‌های پاسخ‌دهی:\n"
    "1. اگر محصولی تمام معیارهای کاربر را برآورده کرد، آن را با اعتماد به نفس پیشنهاد بده.\n"
    "2. اگر هیچ محصولی دقیقاً مطابق معیارها نبود، نزدیک‌ترین گزینه‌ها را پیشنهاد بده و صادقانه بگو کدام معیارها متفاوت هستند (مثلاً «قیمت کمی بالاتر است اما رم مورد نظر را دارد»).\n"
    "3. هرگز نگو «محصولی یافت نشد» مگر اینکه واقعاً لیست محصولات خالی باشد.\n"
    "4. توضیحاتت باید کوتاه، شفاف و مفید باشد (حداکثر ۲-۳ جمله).\n"
    "5. در next_suggestion، یک فیلتر یا اقدام عملی پیشنهاد بده که کاربر می‌تواند برای بهبود نتایج انجام دهد." )

_TEMPLATE_SEARCH = ( "کاربر به دنبال محصولی با این ویژگی‌هاست: {filters}\n"
                     "محصولات بازیابی‌شده:\n{products}\n\n"
                     "حداکثر ۲ محصول را پیشنهاد بده و دلیل انتخاب را شفاف توضیح بده." )
_TEMPLATE_COMPARE = ( "کاربر می‌خواهد بین محصولات زیر مقایسه‌ای انجام دهد:\n{products}\n"
                      "تفاوت‌های کلیدی، نقاط قوت هرکدام و یک جمع‌بندی نهایی ارائه بده." )

# ✅ قالب جدید برای Intent: refine
_TEMPLATE_REFINE = ( "کاربر می‌خواهد نتایج جستجوی قبلی را اصلاح یا محدودتر کند.\n"
                     "درخواست جدید: {refine_query}\n"
                     "فیلترهای فعلی: {filters}\n"
                     "محصولات پیشنهادی قبلی:\n{products}\n\n"
                     "با توجه به درخواست جدید، حداکثر ۲ محصول مرتبط‌تر یا جایگزین پیشنهاد بده." )


class PromptEngine:

    @staticmethod
    def _format_products( products: list[ QdrantProductPayload ] ) -> str:
        parts = []
        for p in products[ :2 ]:
            parts.append( f" | {p.title} | قیمت: {p.price:,} | رنج: {p.price_range} | "
                          f"دوربین: {p.camera_quality} | تگ‌ها: {', '.join(p.tags)}" )
        return "\n".join( parts )

    @classmethod
    def build( cls, intent: str, filters: str | None, products: list[ QdrantProductPayload ] ) -> list[ ChatCompletionMessageParam ]:
        prod_text = cls._format_products( products ) or "محصولی یافت نشد."
        filt = filters or "بدون فیلتر خاص"

        if intent == "compare":
            user_content = _TEMPLATE_COMPARE.format( products=prod_text )
        elif intent == "refine":
            user_content = _TEMPLATE_REFINE.format(
                refine_query="{refine_query_placeholder}",          # ✅ توسط Orchestrator جایگزین می‌شود
                filters=filt,
                products=prod_text,
            )
        else:
            user_content = _TEMPLATE_SEARCH.format( filters=filt, products=prod_text )

        return [
            {
                "role": "system",
                "content": _SYSTEM_BASE
            },
            {
                "role": "user",
                "content": user_content
            },
        ]
