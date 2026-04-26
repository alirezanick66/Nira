"""موتور قالب‌سازی پرامپت‌های محصول‌محور
مسئول: تولید System/User Prompt بر اساس Intent و داده‌های بازیابی‌شده
"""
#─────────────────────  Imports ─────────────────────
from __future__ import annotations
from groq.types.chat import ChatCompletionMessageParam

#───────────────────── Local Imports ─────────────────────
from src.core.vector.qdrant_payload import QdrantProductPayload

# ✅ ‫اصلاح: حذف دستور تکراری JSON (چون در لایه کلاینت به‌صورت ساختاریافته تنظیم شده است)
_SYSTEM_BASE = ( "تو یک دستیار خرید هوشمند، دقیق و همدل هستی. "
                 "تنها از اطلاعات ارائه‌شده استفاده کن و هرگز اطلاعاتی ساختگی تولید نکن." )

_TEMPLATE_SEARCH = ( "کاربر به دنبال محصولی با این ویژگی‌هاست: {filters}\n"
                     "محصولات بازیابی‌شده:\n{products}\n\n"
                     "حداکثر ۲ محصول را پیشنهاد بده و دلیل انتخاب را شفاف توضیح بده." )
_TEMPLATE_COMPARE = ( "کاربر می‌خواهد بین محصولات زیر مقایسه‌ای انجام دهد:\n{products}\n"
                      "تفاوت‌های کلیدی، نقاط قوت هرکدام و یک جمع‌بندی نهایی ارائه بده." )


class PromptEngine:

    @staticmethod
    def _format_products( products: list[ QdrantProductPayload ] ) -> str:
        parts = []
        for p in products[ :2 ]:
            parts.append( f"- ID:{p.product_id} | {p.title} | قیمت: {p.price:,} | رنج: {p.price_range} | "
                          f"دوربین: {p.camera_quality} | تگ‌ها: {', '.join(p.tags)}" )
        return "\n".join( parts )

    @classmethod
    def build( cls, intent: str, filters: str | None, products: list[ QdrantProductPayload ] ) -> list[ ChatCompletionMessageParam ]:
        prod_text = cls._format_products( products )

        if intent == "compare":
            user_content = _TEMPLATE_COMPARE.format( products=prod_text )
        else:
            filt = filters or "بدون فیلتر خاص"
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
