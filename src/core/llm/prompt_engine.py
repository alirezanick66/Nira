""" ‫موتور قالب‌سازی پرامپت‌های چند-دامنه‌ای (Domain-Agnostic)
‫مسئولیت: بارگذاری تمپلیت‌ها از YAML، جایگزینی ایمن متغیرها، و تولید لیست پیام‌های ساختاریافته
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
from string import Template

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.domain_loader import DomainConfig
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.config.logging_config import log_message, LogLevel, LG


class PromptEngine:
    """تولیدکنندهٔ پرامپت‌های پارامتریک بر اساس پیکربندی دامنه"""

    def __init__( self, domain_config: DomainConfig ) -> None:
        self._prompts: dict[ str, object ] = domain_config.prompts
        self._sys_base: str = str( self._prompts.get( "system_base", "" ) )
        raw_templates = self._prompts.get( "templates", {} )
        self._templates: dict[ str, str ] = {
            k: str( v )
            for k, v in ( raw_templates if isinstance( raw_templates, dict ) else {} ).items()
        }
        log_message( LG.LLM, f"PromptEngine بارگذاری شد | {len(self._templates)} تمپلیت فعال", LogLevel.DEBUG )

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
        """‫تولید نهایی لیست پیام‌های System/User برای ارسال به LLM

        Args:
            intent: ‫نیت تشخیص‌داده‌شده (مثلاً search, refine)
            filters: رشتهٔ نمایش فیلترهای متادیتا
            products: لیست محصولات کاندید
            refine_query: ‫کوئری اصلاحی (در صورت refine)

        Returns:
           ‫ لیست دیکشنری‌های role/content استاندارد LLM
        """

        prod_text = self._format_products( products ) or "محصولی یافت نشد."

        context = { "filters": filters, "products": prod_text, "refine_query": refine_query, **kwargs }

        template_str = self._templates.get( intent, self._templates.get( "search", "" ) )
        user_content = Template( template_str ).safe_substitute( context )

        log_message( LG.LLM,
                     f"رندر پرامپت | Intent: {intent} | تمپلیت: {intent if intent in self._templates else 'search (fallback)'}",
                     LogLevel.DEBUG )

        return [ { "role": "system", "content": self._sys_base }, { "role": "user", "content": user_content } ]
