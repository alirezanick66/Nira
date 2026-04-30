"""خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه Token-Based
مسئول: نرمال‌سازی، تشخیص نیت، استخراج فیلترها، مدیریت تضاد و تولید کوئری تمیز
تغییرات کلیدی: جایگزینی Regex با TokenParser، جداسازی کامل دامنه، تزریق وابستگی
"""
from __future__ import annotations

import unicodedata
from typing import cast

from src.config.domain_loader import DomainConfigLoader
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.normalizer import PersianNormalizer
from src.core.nlu.schemas import NLUFilterQuery, MetadataFilters
from src.core.nlu.token_parser import TokenParser
from src.core.nlu.model_masker import ModelMasker
from src.core.nlu.conflict_resolver import ConflictResolver


class NLUPipeline:
    """مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند سازگار با Qdrant
    
    این کلاس کاملاً Stateless طراحی شده و تمام وابستگی‌های دامنه‌ای را در زمان
    راه‌اندازی تزریق می‌کند تا تست‌پذیری حداکثری و وابستگی ضمنی حذف گردد.
    """

    def __init__( self, domain: str = "mobile", config_loader: DomainConfigLoader | None = None ) -> None:
        self._loader = config_loader or DomainConfigLoader()
        self._config = self._loader.load( domain )
        self._normalizer = PersianNormalizer()
        self._parser = TokenParser( self._config )
        self._conflict_resolver = ConflictResolver( self._config )

        # استخراج مقادیر پرتکرار برای دسترسی سریع (O(1))
        self._stop_words = frozenset( cast( list[ str ], self._config.get( "stop_words_semantic", [] ) ) )
        self._intent_keywords = cast( dict[ str, list[ str ] ], self._config.get( "intent_keywords", {} ) )
        self._model_prefixes = frozenset( cast( list[ str ], self._config.get( "model_prefixes", [] ) ) )

        log_message( LG.NLU, f"✅ NLUPipeline برای دامنه '{domain}' آماده است", LogLevel.INFO )

    def process( self, user_input: str ) -> NLUFilterQuery:
        """پردازش کامل کوئری و تولید ساختار فیلتر نهایی

        Args:
            user_input: متن خام ورودی کاربر

        Returns:
            مدل NLUFilterQuery آماده تزریق به لایهٔ بازیابی
        """
        processed = self._preprocess_query( user_input )
        intent = self._detect_intent( processed )

        if intent == "greeting":
            return NLUFilterQuery( intent=intent, semantic_query=processed, is_greeting=True, metadata_filters={}, warnings=[] )

        # ۱. ماسک کردن شماره مدل‌ها برای جلوگیری از تداخل عددی
        mask_res = ModelMasker.mask( processed, self._model_prefixes )
        clean_text = mask_res.masked_text

        # ۲. استخراج فیلترها با TokenParser
        filters = self._parser.parse( clean_text )

        # ۳. حل تضاد فیلترها بر اساس قواعد دامنه
        filters, conflict_report = self._conflict_resolver.resolve( cast( dict[ str, object ], filters ), processed )

        # ۴. ساخت semantic_query تمیز برای بردارسازی
        semantic_query = self._build_semantic_query( processed )

        log_message( LG.NLU, f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters}", LogLevel.DEBUG )

        return NLUFilterQuery( intent=intent,
                               semantic_query=semantic_query,
                               metadata_filters=cast( MetadataFilters, filters ),
                               is_greeting=False,
                               warnings=conflict_report.warnings )

    # ──────────────────────────────────────────────────────────────
    # 🔧 Private Methods
    # ──────────────────────────────────────────────────────────────

    def _preprocess_query( self, text: str ) -> str:
        """نرمال‌سازی کامل + یک‌دست‌سازی یونیکد برای پارسینگ دقیق"""
        normalized = self._normalizer.normalize( text )
        return unicodedata.normalize( "NFKC", normalized ).strip()

    def _detect_intent( self, text: str ) -> str:
        """تشخیص نیت بر اساس کلمات کلیدی کانفیگ‌محور با اولویت صریح"""
        priority_order = ( "greeting", "refine", "compare", "search" )
        tokens = text.split()
        token_set = set( tokens )

        for intent_key in priority_order:
            keywords = self._intent_keywords.get( intent_key, [] )
            for kw in keywords:
                if ' ' not in kw:          # تک‌کلمه
                    if kw in token_set:
                        return intent_key
                else:          # چندکلمه‌ای (مثل "کدوم بهتره")
                    if kw in text:
                        # (اختیاری: تطبیق توکن‌های متوالی، ولی همین کافیست)
                        return intent_key
        return "search"

    def _build_semantic_query( self, processed: str ) -> str:
        """حذف کلمات فیلترساز و متادیتایی از متن برای بردارسازی تمیزتر"""
        parts = [ w for w in processed.split() if w not in self._stop_words ]
        return " ".join( parts ).strip() or processed
