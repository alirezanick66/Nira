"""‫خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه MVP Refinement
‫مسئول: نرمال‌سازی، تشخیص نیت، استخراج Slotها، نگاشت مفاهیم نسبی به فیلترهای عددی

‫تغییرات MVP Refinement:
- پشتیبانی از پارسر هوشمند اعداد/واحد (`UnitParser`)
- تفکیک شماره‌های مدل از قیمت/رم
- مدیریت تضاد فیلترها (`ConflictResolver`)
- بازگشت گزارش هشدارها همراه با فیلترها
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import unicodedata

#───────────────────── Local Imports ─────────────────────
from src.config.knowledge_loader import KnowledgeCache
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.normalizer import PersianNormalizer
from src.core.nlu.schemas import NLUFilterQuery
from src.core.nlu.unit_parser import UnitParser
from src.core.nlu.conflict_resolver import ConflictResolver


class NLUPipeline:
    """‫مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند"""

    def __init__( self ) -> None:
        self._knowledge = KnowledgeCache.get_instance()
<<<<<<< HEAD

        self._price_pattern = re.compile( r'(زیر|بالای|حدود|کمتر|بیشتر)?\s*(\d+(?:\.\d+)?)\s*(میلیون|میلیارد)?\s*(تومان|ت)?' )
        # ✅ بهبود: پشتیبانی از "رم 8 گیگ"، "حداقل 12 گیگ"، "بالای 16 گیگابایت"
        self._ram_pattern = re.compile( r'(?:رم)?\s*(?:حداقل|بالای|حدود)?\s*(\d{1,2})\s*(?:گیگ|gb|گیگابایت)', re.IGNORECASE )
        # ✅ جدید: پشتیبانی از "حافظه 256"، "فضای 1 ترابایت"، "هارد 512 گیگ"
        self._storage_pattern = re.compile(
            r'(?:حافظه(?:ی داخلی)?|فضا|هارد)\s*(?:حداقل|بالای|حدود)?\s*(\d{2,4})\s*(گیگ(?:ابایت)?|ترابایت|tb)?', re.IGNORECASE )

=======
>>>>>>> 6f214f5c40668076497fb925ec68ada607553252
        self._normalizer = PersianNormalizer()
        self._unit_parser = UnitParser()
        self._conflict_resolver = ConflictResolver()

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
            return NLUFilterQuery(
                intent=intent,
                semantic_query=processed,
                is_greeting=True,
                metadata_filters={},
                warnings=[],
            )

        # ‫1) استخراج اولیه فیلترها
        filters = self._extract_slots( processed )

<<<<<<< HEAD
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
=======
        # ‫2) حل تضاد فیلترها (MVP Refinement #5)
        filters, conflict_report = self._conflict_resolver.resolve( filters, processed )
>>>>>>> 6f214f5c40668076497fb925ec68ada607553252

        # ‫3) ساخت semantic_query تمیز
        semantic_query = self._build_semantic_query( processed )

        log_message(
            LG.NLU,
            f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters} | "
            f"Conflicts: {len(conflict_report.conflicts)}",
            LogLevel.DEBUG,
        )

        return NLUFilterQuery(
            intent=intent,
            semantic_query=semantic_query,
            metadata_filters=filters,
            is_greeting=False,
            warnings=conflict_report.warnings,
        )

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

    def _build_semantic_query( self, processed: str ) -> str:
        """‫حذف کلمات فیلترساز از متن برای بردارسازی تمیزتر"""
        stop_words = {
            # ‫نشانگرهای قیمت
            "زیر",
            "بالای",
            "کمتر",
            "بیشتر",
            "تومان",
            "تومن",
            "ت",
            "حدود",
            "حداقل",
            "حداکثر",
            "تا",
            "الی",
            # ‫واحدها
            "میلیون",
            "میلیارد",
            "هزار",
            # ‫کلمات اضافه
            "از",
            "ولی",
            "اما",
        }
        semantic_parts = [ w for w in processed.split() if w not in stop_words ]
        return " ".join( semantic_parts ).strip() or processed

    def _extract_slots( self, text: str ) -> dict[ str, object ]:
        """‫استخراج فیلترها با پارسر هوشمند MVP Refinement"""
        filters: dict[ str, object ] = {}

<<<<<<< HEAD
        # ✅ تشخیص برندهای منفی‌شده (انعطاف‌پذیرتر برای محاوره)
        neg_brands: list[ str ] = []
=======
        # ────────── 1. تشخیص برند ──────────
>>>>>>> 6f214f5c40668076497fb925ec68ada607553252
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

<<<<<<< HEAD
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
=======
        # ────────── 2. استخراج قیمت با UnitParser ──────────
        # ‫(پشتیبانی از «سی میلیون»، «حدود ۴۰-۵۰»، «۳۰تومن» + اعداد مدل ایمن)
        price_filter = self._unit_parser.extract_price_filter( text )
        if not price_filter.is_empty:
            filters[ "price" ] = price_filter.to_dict()

        # ────────── 3. استخراج رم با تفکیک واحد ──────────
        ram_value = self._unit_parser.extract_memory_filter( text, key="ram" )
        if ram_value is not None:
            # ‫اگر کاربر «مگابایت» گفت، احتمالاً اشتباه کرده یا منظور حافظه نیست
            # ‫فقط GB رو به عنوان رم می‌پذیریم (در عمل MB rare است)
            if ram_value.unit == "GB":
                filters[ "ram_gb" ] = ram_value.value
            elif ram_value.unit == "MB":
                # ‫تبدیل احتمالی - معمولاً اشتباه تایپی
                filters[ "ram_gb" ] = max( 1, ram_value.value // 1024 )

        # ────────── 4. استخراج حافظه با تفکیک واحد ──────────
        storage_value = self._unit_parser.extract_memory_filter( text, key="storage" )
        if storage_value is not None:
            if storage_value.unit == "TB":
                filters[ "storage_gb" ] = storage_value.value * 1024
            elif storage_value.unit == "GB":
                filters[ "storage_gb" ] = storage_value.value
            elif storage_value.unit == "MB":
                # ‫MB در حافظه گوشی غیرواقعی است → نادیده بگیر
                pass

        # ────────── 5. باتری ──────────
        battery_value = self._unit_parser.extract_battery_filter( text )
        if battery_value is not None:
            filters[ "battery_mah" ] = { ">=": battery_value.value }

        # ────────── 6. مفاهیم کیفی ──────────
        for keyword, rule in self._knowledge.qualitative_mappings.items():
            if keyword in text:
                for key, val in rule.items():
                    if isinstance( val, dict ):
                        current = filters.setdefault( key, {} )
                        if isinstance( current, dict ):
                            current.update( val )
                    else:
                        filters[ key ] = val

        # ────────── 7. قواعد استفاده ──────────
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
>>>>>>> 6f214f5c40668076497fb925ec68ada607553252

        return filters
