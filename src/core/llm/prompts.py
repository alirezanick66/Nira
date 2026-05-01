"""موتور قالب‌سازی پرامپت‌های چند-دامنه‌ای (Domain-Agnostic)
مسئولیت: بارگذاری تمپلیت‌ها از YAML، جایگزینی ایمن متغیرها، و تولید لیست پیام‌های ساختاریافته
"""
from __future__ import annotations
from string import Template
from typing import cast

#───────────────────── Local Imports ─────────────────────
from src.config.domain_loader import ConfigDict
from src.core.vector.qdrant_payload import QdrantProductPayload


class PromptEngine:
    """تولیدکنندهٔ پرامپت‌های پارامتریک بر اساس پیکربندی دامنه"""

    def __init__( self, domain_config: ConfigDict ) -> None:
        self._prompts = cast( dict[ str, str ], domain_config.get( "prompts", {} ) )
        self._sys_base = self._prompts.get( "system_base", "" )
        self._templates = cast( dict[ str, str ], self._prompts.get( "templates", {} ) )

    @staticmethod
    def _format_products( products: list[ QdrantProductPayload ] ) -> str:
        """فرمت‌بندی لیست محصولات برای تزریق به پرامپت"""
        parts: list[ str ] = []
        for p in products[ :2 ]:
            tags_str = ", ".join( p.tags ) if p.tags else "بدون تگ"
            parts.append( f"| {p.title} | قیمت: {p.price:,} | رنج: {p.price_range} | "
                          f"دوربین: {p.camera_quality} | تگ‌ها: {tags_str}" )
        return "\n".join( parts )

    def render( self,
                intent: str,
                filters: str,
                products: list[ QdrantProductPayload ],
                refine_query: str = "",
                **kwargs: str ) -> list[ dict[ str, str ] ]:
        """ ‫تولید نهایی لیست پیام‌های System/User برای ارسال به LLM"""
        prod_text = self._format_products( products ) or "محصولی یافت نشد."
        context = { "filters": filters, "products": prod_text, "refine_query": refine_query, **kwargs }

        template_str = self._templates.get( intent, self._templates.get( "search", "" ) )
        user_content = Template( template_str ).safe_substitute( context )

        return [ { "role": "system", "content": self._sys_base }, { "role": "user", "content": user_content } ]
