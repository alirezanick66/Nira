"""خط لوله درک زبان طبیعی (NLU Pipeline) - نسخه Token-Based
مسئول: نرمال‌سازی، تشخیص نیت، استخراج فیلترها، مدیریت تضاد و تولید کوئری تمیز
تغییرات کلیدی: جایگزینی Regex با TokenParser، جداسازی کامل دامنه، تزریق وابستگی

⚠️ منسوخ‌شده (Deprecated): این کلاس به‌نفع LLMNLUExtractor (src/core/nlu/llm_extractor.py) کنار گذاشته شده است.
لطفاً برای کد جدید از LLMNLUExtractor استفاده کنید.
"""
#─────────────────────imports─────────────────────
from __future__ import annotations
import warnings
import unicodedata
from typing import cast
import numpy as np

#─────────────────────local imports─────────────────────
from src.config.domain_loader import DomainConfigLoader
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.normalizer import PersianNormalizer
from src.core.nlu.schemas import NLUFilterQuery, MetadataFilters
from src.core.nlu.token_parser import TokenParser
from src.core.nlu.model_masker import ModelMasker
from src.core.nlu.conflict_resolver import ConflictResolver
from src.services.embedding_service import EmbeddingService


class NLUPipeline:
    """مدیریت پردازش کوئری کاربر و تولید فیلتر هوشمند سازگار با ‫ Qdrant
    
   ‫ این کلاس کاملاً Stateless طراحی شده و تمام وابستگی‌های دامنه‌ای را در زمان
   ‫ راه‌اندازی تزریق می‌کند تا تست‌پذیری حداکثری و وابستگی ضمنی حذف گردد.
    """

    def __init__(
        self,
        domain: str = "mobile",
        config_loader: DomainConfigLoader | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        warnings.warn(
            "NLUPipeline منسوخ شده است. لطفاً از LLMNLUExtractor استفاده کنید.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._loader = config_loader or DomainConfigLoader()
        self._config = self._loader.load( domain )
        self._normalizer = PersianNormalizer()
        self._parser = TokenParser( self._config )
        self._conflict_resolver = ConflictResolver( self._config )
        self._embedder = embedding_service

        # ‫استخراج مقادیر پرتکرار برای دسترسی سریع (O(1))
        self._stop_words = frozenset( cast( list[ str ], self._config.get( "stop_words_semantic", [] ) ) )
        self._model_prefixes = frozenset( cast( list[ str ], self._config.get( "model_prefixes", [] ) ) )
        self.intent_cfg = cast( dict[ str, dict ], self._config.get( "intent_keywords", {} ) )
        # 🧠 پیش‌بارگذاری بردارهای معناری در زمان Startup
        self._semantic_cache: dict[ str, np.ndarray ] = {}
        self._semantic_thresholds: dict[ str, float ] = {}
        if self._embedder:
            self._preload_semantic_vectors()

        self._directive_cache: dict[ str, np.ndarray ] = {}
        self._directive_threshold: float = 0.75
        if self._embedder:
            self._preload_directive_vectors()
        log_message( LG.NLU, f"✅ NLUPipeline برای دامنه '{domain}' آماده است", LogLevel.INFO )

    def _preload_semantic_vectors( self ) -> None:
        """تبدیل مثال‌های معیار هر Intent به بردار و کش در RAM"""

        for intent_name, cfg in self.intent_cfg.items():
            examples = cfg.get( "canonical_examples", [] )
            if examples:
                # ‫مدل E5 به‌طور خودکار پیشوند query: را اضافه می‌کند
                vecs = self._embedder.encode( examples, is_query=True )          # type: ignore
                self._semantic_cache[ intent_name ] = np.array( vecs, dtype=np.float32 )
            self._semantic_thresholds[ intent_name ] = cfg.get( "threshold", 0.72 )

    def process( self, user_input: str ) -> NLUFilterQuery:
        """پردازش کامل کوئری و تولید ساختار فیلتر نهایی"""
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

        # ۴. تشخیص معناری دایرکتیو مرتب‌سازی (جایگزین حلقهٔ رشته‌ای)

        has_limit = any( w in self._stop_words for w in processed.split() )
        has_digit = any( c.isdigit() or c in "۰۱۲۳۴۵۶۷۸۹" for c in processed )
        if has_limit and has_digit:
            sort_directive = None
        else:
            sort_directive = self._detect_sort_directive( processed )

        # ۵. حذف تضاد price_range در صورت فعال‌بودن Sort قیمت
        if ( sort_directive and sort_directive.get( "key" ) == "price"
             and "price" not in filters          # ← اگه price عددی صریح هست، price_range هم نگه دار
             and "price_range" in filters ):
            del filters[ "price_range" ]
            log_message( LG.NLU, "🧹 حذف price_range به دلیل فعال‌بودن دایرکتیو مرتب‌سازی قیمت", LogLevel.DEBUG )

        # ۶. ساخت semantic_query تمیز برای بردارسازی
        semantic_query = self._build_semantic_query( processed )

        log_message( LG.NLU, f"✅ NLU تکمیل | Intent: {intent} | Filters: {filters} | Sort: {sort_directive}", LogLevel.DEBUG )

        return NLUFilterQuery( intent=intent,
                               semantic_query=semantic_query,
                               metadata_filters=cast( MetadataFilters, filters ),
                               is_greeting=False,
                               warnings=conflict_report.warnings,
                               sort_directive=sort_directive )

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
        intent_keywords_raw = cast( dict[ str, dict ], self._config.get( "intent_keywords", {} ) )
        tokens = text.split()
        token_set = set( tokens )

        #‫ ۱. Fast-Path (Rule/Keyword)
        for intent_key in priority_order:
            cfg = intent_keywords_raw.get( intent_key, {} )
            keywords = cfg.get( "keywords_fast", cfg ) if isinstance( cfg, dict ) else cfg
            for kw in keywords:
                if ' ' not in kw:          # تک‌کلمه
                    if kw in token_set:
                        return intent_key
                else:          # چندکلمه‌ای (مثل "کدوم بهتره")
                    if kw in text:
                        # (اختیاری: تطبیق توکن‌های متوالی، ولی همین کافیست)
                        return intent_key

        # ‫۲. Semantic Fallback (Embedding)
        if self._embedder and self._semantic_cache:
            query_vec = np.array( self._embedder.encode( [ text ], is_query=True )[ 0 ], dtype=np.float32 )
            max_sim = -1.0
            best_intent = "search"

            for intent_name, cached_vecs in self._semantic_cache.items():
                sims = cached_vecs @ query_vec
                current_max = float( np.max( sims ) )
                if current_max > max_sim:
                    max_sim = current_max
                    best_intent = intent_name

            threshold = self._semantic_thresholds.get( best_intent, 0.70 )
            # فقط اگر امتیاز از آستانه گذشت، Intent تغییر می‌کند. در غیر این صورت search می‌ماند.
            if max_sim >= threshold:
                log_message( LG.NLU, f"🧠 تشخیص نیت معناری | Intent: {best_intent} | Similarity: {max_sim:.3f}", LogLevel.DEBUG )
                return best_intent
        return "search"

    def _build_semantic_query( self, processed: str ) -> str:
        """حذف کلمات فیلترساز و متادیتایی از متن برای بردارسازی تمیزتر"""
        parts = [ w for w in processed.split() if w not in self._stop_words ]
        return " ".join( parts ).strip() or processed

    def get_intent_scores( self, text: str ) -> dict[ str, float ]:
        """فقط برای دیباگ و کالیبراسیون threshold — در production استفاده نشه"""
        if not self._embedder or not self._semantic_cache:
            return {}
        processed = self._preprocess_query( text )
        query_vec = np.array( self._embedder.encode( [ processed ], is_query=True )[ 0 ], dtype=np.float32 )
        return { intent: float( np.max( vecs @ query_vec ) ) for intent, vecs in self._semantic_cache.items() }

    def _preload_directive_vectors( self ) -> None:
        """تبدیل مثال‌های دایرکتیو به بردار و کش در RAM"""
        directives = cast( dict[ str, list ], self._config.get( "directive_examples", {} ) )
        for key, examples in directives.items():
            if examples:
                vecs = self._embedder.encode( examples, is_query=True )          # type: ignore
                self._directive_cache[ key ] = np.array( vecs, dtype=np.float32 )

    def _detect_sort_directive( self, text: str ) -> dict[ str, str ] | None:
        """تشخیص معناری دایرکتیو مرتب‌سازی با مدل E5"""
        if not self._embedder or not self._directive_cache:
            return None

        query_vec = np.array( self._embedder.encode( [ text ], is_query=True )[ 0 ], dtype=np.float32 )
        best_key, max_sim = None, -1.0

        for key, cached_vecs in self._directive_cache.items():
            current_max = float( np.max( cached_vecs @ query_vec ) )
            if current_max > max_sim:
                max_sim = current_max
                best_key = key

        if max_sim >= self._directive_threshold and best_key is not None:
            if "asc" in best_key:
                return { "key": "price", "order": "asc" }
            if "desc" in best_key:
                return { "key": "price", "order": "desc" }
        return None

    def get_domain_config( self ) -> dict:
        """‫دسترسی عمومی به کانفیگ دامنه"""
        return self._config
