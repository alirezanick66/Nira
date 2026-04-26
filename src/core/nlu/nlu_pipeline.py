"""‫خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه MVP مبتنی بر قواعد
‫مسئول: نرمال‌سازی، تشخیص نیت، استخراج Slotها، نگاشت مفاهیم نسبی به فیلترهای عددی
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import re
import unicodedata

#───────────────────── Local Imports ─────────────────────
from src.config.knowledge_loader import KnowledgeCache
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.normalizer import PersianNormalizer
from src.core.nlu.schemas import NLUFilterQuery


class NLUPipeline:
    """‫مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند"""

    def __init__( self ) -> None:
        self._knowledge = KnowledgeCache.get_instance()

        self._price_pattern = re.compile( r'(زیر|بالای|حدود|کمتر|بیشتر)?\s*(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)?\s*(تومان|ت)?' )
        # ✅ بهبود: پشتیبانی از "رم 8 گیگ"، "حداقل 12 گیگ"، "بالای 16 گیگابایت"
        self._ram_pattern = re.compile( r'(?:رم)?\s*(?:حداقل|بالای|حدود)?\s*(\d{1,2})\s*(?:گیگ|gb|گیگابایت)', re.IGNORECASE )
        # ✅ جدید: پشتیبانی از "حافظه 256"، "فضای 1 ترابایت"، "هارد 512 گیگ"
        self._storage_pattern = re.compile(
            r'(?:حافظه(?:ی داخلی)?|فضا|هارد)\s*(?:حداقل|بالای|حدود)?\s*(\d{2,4})\s*(گیگ(?:ابایت)?|ترابایت|tb)?', re.IGNORECASE )

        self._normalizer = PersianNormalizer()

        log_message( LG.NLU, "NLUPipeline آماده پردازش کوئری‌ها است", LogLevel.INFO )

    #───────────────────── public  methods ─────────────────────
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
        semantic_query = processed

        brand_not = filters.get( "brand_not", [] )
        if isinstance( brand_not, str ):
            brand_not = [ brand_not ]
        elif not isinstance( brand_not, ( list, tuple, set ) ):
            brand_not = []

        for brand in brand_not:
            for neg_kw in self._knowledge.negation_keywords:
                semantic_query = semantic_query.replace( f"{brand} {neg_kw}", "" ).replace( f"{neg_kw} {brand}",
                                                                                            "" ).replace( f"{brand}{neg_kw}", "" )
        semantic_query = " ".join( semantic_query.split() )          # نرمال‌سازی فاصله‌های اضافی

        # حذف کلمات فیلترساز (کدهای قبلی خودت)
        stop_words = { "زیر", "بالای", "کمتر", "بیشتر", "تومان", "ت", "حدود" }
        semantic_parts = [ w for w in semantic_query.split() if w not in stop_words ]
        semantic_query = " ".join( semantic_parts ).strip() or semantic_query

        log_message( LG.NLU, f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters}", LogLevel.DEBUG )

        return NLUFilterQuery( intent=intent, semantic_query=semantic_query, metadata_filters=filters, is_greeting=False )

    #───────────────────── private  methods ─────────────────────
    def _preprocess_query( self, text: str ) -> str:
        """‫نرمال‌سازی کامل + تبدیل اعداد به لاتین برای پارسینگ دقیق"""
        normalized = self._normalizer.normalize( text )
        return unicodedata.normalize( "NFKC", normalized )

    def _detect_intent( self, text: str ) -> str:
        # ✅ ترتیب اولویت صریح: greeting → refine → search → compare
        priority_order = [ "greeting", "refine", "search", "compare" ]
        for intent_key in priority_order:
            keywords = self._knowledge.intent_keywords.get( intent_key, [] )
            if any( kw in text for kw in keywords ):
                return intent_key
        return "search"

    def _extract_slots( self, text: str ) -> dict[ str, object ]:
        filters: dict[ str, object ] = {}

        # ✅ تشخیص برندهای منفی‌شده (انعطاف‌پذیرتر برای محاوره)
        neg_brands: list[ str ] = []
        for brand in self._knowledge.brands:
            if brand in text and any( neg_kw in text for neg_kw in self._knowledge.negation_keywords ):
                neg_brands.append( brand )
        if neg_brands:
            filters[ "brand_not" ] = neg_brands
            # ✅ جلوگیری از تداخل: اگر برند مثبت قبلاً ثبت شده، حذفش کن
            if filters.get( "brand" ) in neg_brands:
                del filters[ "brand" ]

        # ۲. تشخیص برند مثبت (اگر در لیست منفی‌ها نیست)
        for brand in self._knowledge.brands:
            if brand in text and brand not in neg_brands:
                filters[ "brand" ] = brand
                break

        # ۳. استخراج قیمت (بازهٔ صریح اولویت دارد)
        range_match = re.search( r'بین\s*(\d+)\s*تا\s*(\d+)\s*(میلیون|میلیارد|تومان|ت)?', text )
        if range_match:
            min_val = float( range_match.group( 1 ) )
            max_val = float( range_match.group( 2 ) )
            unit = range_match.group( 3 ) or ""
            mult = 1_000_000 if "میلیون" in unit else 1_000_000_000 if "میلیارد" in unit else 1
            filters[ "price" ] = { ">=": min_val * mult, "<=": max_val * mult }
        else:
            price_match = self._price_pattern.search( text )
            if price_match:
                op_str = price_match.group( 1 ) or ""
                amount = float( price_match.group( 2 ) )
                unit_str = price_match.group( 3 ) or ""
                currency_str = price_match.group( 4 ) or ""
                has_indicator = bool( op_str ) or "میلیون" in unit_str or "تومان" in currency_str or "ت" in currency_str
                if has_indicator:
                    val = amount * ( 1_000_000_000 if "میلیارد" in unit_str else 1_000_000 if "میلیون" in unit_str else 1 )
                    op_dict = filters.setdefault( "price", {} )
                    if isinstance( op_dict, dict ):
                        if "زیر" in op_str or "کمتر" in op_str: op_dict[ "<" ] = val
                        elif "بالای" in op_str or "بیشتر" in op_str: op_dict[ ">=" ] = val
                        else: op_dict[ "<" ] = val * 1.5

        # ۴. استخراج رم و حافظه
        if ram_match := self._ram_pattern.search( text ):
            filters[ "ram_gb" ] = int( ram_match.group( 1 ) )
        if storage_match := self._storage_pattern.search( text ):
            val = int( storage_match.group( 1 ) )
            unit = ( storage_match.group( 2 ) or "" ).lower()
            if "ترابایت" in unit or "tb" in unit: val *= 1000
            filters[ "storage_gb" ] = val

        # ۵. نگاشت کیفی و قواعد استفاده (بدون بازنویسی فیلترهای صریح)
        for kw_dict in ( self._knowledge.qualitative_mappings, self._knowledge.use_case_rules ):
            for keyword, rule in kw_dict.items():
                if keyword in text:
                    for key, val in rule.items():
                        if key not in filters:
                            if isinstance( val, dict ):
                                current = filters.setdefault( key, {} )
                                if isinstance( current, dict ): current.update( val )
                            elif isinstance( val, list ):
                                tags = filters.setdefault( "tags", [] )
                                if isinstance( tags, list ):
                                    tags.extend( t for t in val if t not in tags )
                            else:
                                filters[ key ] = val

        return filters
