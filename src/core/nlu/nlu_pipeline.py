"""‫خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه MVP مبتنی بر قواعد
‫مسئول: نرمال‌سازی، تشخیص نیت، استخراج Slotها، نگاشت مفاهیم نسبی به فیلترهای عددی
"""
from __future__ import annotations

import re
import unicodedata

from src.config.knowledge_loader import KnowledgeCache
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.normalizer import persian_normalizer
from src.core.nlu.schemas import NLUFilterQuery


class NLUPipeline:
    """‫مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند"""

    def __init__( self ) -> None:
        self._knowledge = KnowledgeCache.get_instance()
        self._price_pattern = re.compile( r'(زیر|بالای|حدود|کمتر|بیشتر)?\s*(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)?\s*(تومان|ت)?' )
        self._ram_pattern = re.compile( r'(\d{1,2})\s*(?:گیگ|gb)\s*رم', re.IGNORECASE )

    def _preprocess_query( self, text: str ) -> str:
        """‫نرمال‌سازی کامل + تبدیل اعداد به لاتین برای پارسینگ دقیق"""
        normalized = persian_normalizer.normalize( text )
        return unicodedata.normalize( "NFKC", normalized )

    def _detect_intent( self, text: str ) -> str:
        for intent, keywords in self._knowledge.intent_keywords.items():
            if any( kw in text for kw in keywords ):
                return intent
        return "search"

    def _extract_slots( self, text: str ) -> dict[ str, object ]:
        filters: dict[ str, object ] = {}

        # ۱. تشخیص برند
        for brand in self._knowledge.brands:
            if brand in text:
                filters[ "brand" ] = brand
                break

        # ۲. ✅ استخراج قیمت هوشمند (پشتیبانی از میلیون/میلیارد)
        price_match = self._price_pattern.search( text )
        if price_match:
            op_str = price_match.group( 1 ) or ""
            amount = float( price_match.group( 2 ) )
            unit_str = price_match.group( 3 ) or ""
            currency_str = price_match.group( 4 ) or ""

            # بررسی وجود نشانه‌ی صریح قیمت
            has_price_indicator = ( bool( op_str ) or "میلیون" in unit_str or "تومان" in currency_str or "ت" in currency_str )

            if has_price_indicator:
                val = amount
                if "میلیارد" in unit_str:
                    val *= 1_000_000_000
                elif "میلیون" in unit_str:
                    val *= 1_000_000

                op_dict = filters.setdefault( "price", {} )
                if isinstance( op_dict, dict ):
                    if "زیر" in op_str or "کمتر" in op_str:
                        op_dict[ "<" ] = int( val )
                    elif "بالای" in op_str or "بیشتر" in op_str:
                        op_dict[ ">=" ] = int( val )
                    else:
                        op_dict[ "<" ] = int( val * 1.5 )

        # ۳. استخراج رم
        if ram_match := self._ram_pattern.search( text ):
            filters[ "ram_gb" ] = int( ram_match.group( 1 ) )

        # ۴. نگاشت مفاهیم کیفی
        for keyword, rule in self._knowledge.qualitative_mappings.items():
            if keyword in text:
                for key, val in rule.items():
                    if isinstance( val, dict ):
                        current = filters.setdefault( key, {} )
                        if isinstance( current, dict ):
                            current.update( val )
                    else:
                        filters[ key ] = val

        # ۵. قواعد استفاده
        for keyword, rule in self._knowledge.use_case_rules.items():
            if keyword in text:
                for key, val in rule.items():
                    if isinstance( val, dict ):
                        current = filters.setdefault( key, {} )
                        if isinstance( current, dict ):
                            current.update( val )
                    elif isinstance( val, list ):
                        tags = filters.setdefault( "tags", [] )
                        if isinstance( tags, list ):
                            tags.extend( [ t for t in val if t not in tags ] )
                    else:
                        filters[ key ] = val

        return filters

    def process( self, user_input: str ) -> NLUFilterQuery:
        """‫پردازش کامل کوئری و تولید ساختار فیلتر

        Args:
            user_input: متن خام کاربر

        Returns:
            مدل NLUFilterQuery آماده استفاده
        """
        processed = self._preprocess_query( user_input )
        intent = self._detect_intent( processed )

        if intent == "greeting":
            return NLUFilterQuery( intent=intent, semantic_query=processed, is_greeting=True, metadata_filters={} )

        filters = self._extract_slots( processed )

        # حذف کلمات فیلترساز از semantic_query برای جلوگیری از نویز در بردارسازی
        stop_words = { "زیر", "بالای", "کمتر", "بیشتر", "تومان", "ت", "حدود" }
        semantic_parts = [ w for w in processed.split() if w not in stop_words ]
        semantic_query = " ".join( semantic_parts ).strip() or processed

        log_message( LG.NLU, f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters}", LogLevel.DEBUG )

        return NLUFilterQuery( intent=intent, semantic_query=semantic_query, metadata_filters=filters, is_greeting=False )


nlu_pipeline = NLUPipeline()
