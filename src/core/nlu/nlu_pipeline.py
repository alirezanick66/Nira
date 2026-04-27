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
        self._normalizer = PersianNormalizer()
        self._unit_parser = UnitParser()
        self._conflict_resolver = ConflictResolver()

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

        # ‫2) حل تضاد فیلترها (MVP Refinement #5)
        filters, conflict_report = self._conflict_resolver.resolve( filters, processed )

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
        for intent, keywords in self._knowledge.intent_keywords.items():
            if any( kw in text for kw in keywords ):
                return intent
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

        # ────────── 1. تشخیص برند ──────────
        for brand in self._knowledge.brands:
            if brand in text:
                filters[ "brand" ] = brand
                break

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

        return filters
