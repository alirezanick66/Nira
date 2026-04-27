"""‫خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه MVP Refinement
‫مسئول: نرمال‌سازی، تشخیص نیت، استخراج Slotها، نگاشت مفاهیم نسبی به فیلترهای عددی

‫تغییرات MVP Refinement:
- پشتیبانی از پارسر کانفیگ‌محور‫ (`SlotExtractor`)
- تفکیک شماره‌های مدل از قیمت/رم
- مدیریت تضاد فیلترها (`ConflictResolver`)
- بازگشت گزارش هشدارها همراه با فیلترها
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
from src.core.nlu.conflict_resolver import ConflictResolver
from src.core.nlu.slot_extractor import SlotExtractor, SlotRule
from src.core.nlu.model_masker import ModelMasker
from src.core.nlu.schemas import MetadataFilters, MetadataFilterValue
from typing import cast


class NLUPipeline:
    """‫مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند"""

    def __init__( self ) -> None:
        self._knowledge = KnowledgeCache.get_instance()
        self._normalizer = PersianNormalizer()
        #‫بارگذاری قوانین اسلات از کانفیگ دامنه
        slot_rules_data = self._knowledge.domain_data.get( "slot_definitions", [] )
        slot_rules = [ SlotRule.model_validate( r ) for r in slot_rules_data ]
        self._slot_extractor = SlotExtractor( rules=slot_rules )
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

        # ‫2) حل تضاد فیلترها (MVP Refinement #5)
        filters, conflict_report = self._conflict_resolver.resolve( filters, processed )

        # ‫3) ساخت semantic_query تمیز
        semantic_query = self._build_semantic_query( processed )

        log_message( LG.NLU, f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters} | "
                     f"Conflicts: {len(conflict_report.conflicts)}", LogLevel.DEBUG )

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

    def _extract_slots( self, text: str ) -> MetadataFilters:
        """‫استخراج فیلترها با پارسر هوشمند MVP Refinement"""
        filters: MetadataFilters = {}

        # ────────── 0. ماسک کردن شماره مدل‌ها قبل از استخراج اسلات ──────────
        mask_res = ModelMasker.mask( text, frozenset( self._knowledge.brands ) )
        text_for_slots = re.sub( r'__MODEL_\d+__', '', mask_res.masked_text )
        text_for_slots = re.sub( r'\s+', ' ', text_for_slots ).strip()

        # ────────── 1. استخراج اسلات‌های کانفیگ‌محور ──────────
        slot_filters = self._slot_extractor.extract( text_for_slots )
        filters.update( slot_filters )

        # ────────── 2. تشخیص برند ──────────
        neg_brands: list[ str ] = []
        for brand in self._knowledge.brands:
            if brand in text and any( neg_kw in text for neg_kw in self._knowledge.negation_keywords ):
                neg_brands.append( brand )
        if neg_brands:
            filters[ "brand_not" ] = neg_brands
            if filters.get( "brand" ) in neg_brands:
                del filters[ "brand" ]

        # ۳. تشخیص برند مثبت (اگر در لیست منفی‌ها نیست)
        for brand in self._knowledge.brands:
            if brand in text and brand not in neg_brands:
                filters[ "brand" ] = brand
                break

        # ────────── 6. مفاهیم کیفی ──────────
        for keyword, rule in self._knowledge.qualitative_mappings.items():
            if keyword in text:
                for key, val in rule.items():
                    if isinstance( val, dict ):
                        current = filters.setdefault( key, {} )
                        if isinstance( current, dict ):
                            current.update( val )
                    else:
                        filters[ key ] = cast( MetadataFilterValue, val )

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
                        filters[ key ] = cast( MetadataFilterValue, val )

        return filters
