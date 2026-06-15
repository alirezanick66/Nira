"""ارکستراتور اصلی LLM
‫مسئول: مدیریت چرخه کامل Memory → Prompt → Groq → Gemini(Fallback) → Validation
"""
#──────────────────────────────────────────  Imports ──────────────────────────────────────────
from __future__ import annotations
import hashlib
import json
from pydantic import TypeAdapter
from typing import cast
from string import Template
from groq.types.chat import ChatCompletionMessageParam
import random
#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.settings import get_settings
from src.config.domain_loader import DomainConfig
from src.config.logging_config import log_message, LogLevel, LG
from src.core.llm.clients import GroqClient, GeminiClient
from src.core.llm.memory import ConversationMemory
from src.core.llm.prompt_engine import PromptEngine
from src.core.llm.schemas import LLMResponseSchema, LLMExtractSchema, IntentType, MetadataFilters
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.utils.normalizer import PersianNormalizer
from src.services.semantic_cache_service import AsyncTTLCache


class LLMOrchestrator:

    def __init__(
        self,
        domain_config: DomainConfig,
        groq_client: GroqClient | None = None,
        gemini_client: GeminiClient | None = None,
        memory: ConversationMemory | None = None,
        normalizer: PersianNormalizer | None = None,
        semantic_cache: AsyncTTLCache | None = None,
    ) -> None:
        """ارکستراتور اصلی LLM با پشتیبانی از تزریق وابستگی (DI) برای تست‌پذیری

        Args:
            domain_config: پیکربندی دامنه بارگذاری‌شده
            groq_client: ‫کلاینت Groq (اختیاری)
            gemini_client: ‫کلاینت Gemini (اختیاری)
            memory: ‫سرویس حافظه مکالمه (اختیاری)
            normalizer: ‫نرمال‌ساز متن فارسی (اختیاری)
            semantic_cache: ‫سرویس کش معنایی (اختیاری)
        """
        self._config = domain_config
        self._settings = get_settings()
        self._memory = memory or ConversationMemory( max_turns=3 )
        self._groq = groq_client or GroqClient()
        self._gemini = gemini_client or GeminiClient()
        self._validator = TypeAdapter( LLMResponseSchema )
        self._extract_validator = TypeAdapter( LLMExtractSchema )
        self._prompt_engine = PromptEngine( domain_config )
        self._normalizer = normalizer or PersianNormalizer()
        self._semantic_cache = semantic_cache
        #intent
        self._greeting_keywords = frozenset( self._config.intent_keywords.get( "greeting", {} ).get( "keywords_fast", [] ) )
        self._greeting_responses: list[ str ] = self._config.greeting_responses
        self._general_chat_responses: list[ str ] = self._config.general_chat_responses

        self._domain_schema_str = self._build_domain_schema()
        self._price_ceiling_multiplier: float = domain_config.price_ceiling_multiplier

        log_message( LG.LLM, "سرویس LLMOrchestrator آماده پذیرش درخواست است", LogLevel.INFO )

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    def get_non_search_response( self, intent: IntentType ) -> str:
        """‫انتخاب تصادفی پاسخ از YAML برای intentهای غیرجستجو (بدون فراخوانی LLM)"""
        if intent == IntentType.GENERAL_CHAT:
            return random.choice( self._general_chat_responses )
        return random.choice( self._greeting_responses )

    async def get_session_history( self, session_id: str ) -> list[ dict[ str, str ] ]:
        """دریافت تاریخچه مکالمه نشست فعال"""
        return await self._memory.get_history( session_id )

    async def get_session_last_filters( self, session_id: str ) -> dict:
        """دریافت آخرین فیلترهای جستجوی موفق نشست"""
        return await self._memory.get_last_filters( session_id )

    async def save_turn(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
    ) -> None:
        """ثبت یک نوبت مکالمه (user + assistant) بدون فراخوانی LLM

        برای intentهایی مثل greeting و clarification که مستقیم پاسخ می‌دهند
        و generate() صدا نمی‌شود — تاریخچه مکالمه ناقص نماند.
        """
        await self._memory.add_message( session_id, "user", user_msg )
        await self._memory.add_message( session_id, "assistant", assistant_msg )

    # ──────────────────────────────────────  فاز 1:متدهای جدید استخراج نیت/فیلتر + چک   ──────────────────────────────────────
    async def extract(
        self,
        query: str,
        session_id: str,
        last_filters: MetadataFilters | None = None,
        last_products: list[ str ] | None = None,
        history: list[ dict[ str, str ] ] | None = None,
    ) -> LLMExtractSchema:
        """استخراج نیت، فیلترها و کوئری معنایی با اعتبارسنجی سخت‌گیرانه

        Args:
            query: متن ورودی کاربر
            session_id: شناسه نشست فعال
            last_filters: فیلترهای اعمال‌شده در مرحله قبل
            last_products: محصولات پیشنهادی قبلی
            history: تاریخچه مکالمه

        Returns:
            ‫LLMExtractSchema اعتبارسنجی‌شده

        Raises:
            RuntimeError: ‫در صورت عدم دسترسی به سرویس‌های LLM
            ValueError: ‫در صورت خروجی JSON نامعتبر
        """
        normalized = self._normalizer.normalize( query )

        # ‫۱. Fast-Path Greeting Check
        if self._is_greeting_fast( normalized ):
            log_message( LG.LLM, "👋 Greeting شناسایی شد (Fast-Path) | بدون فراخوانی LLM", LogLevel.DEBUG )
            return LLMExtractSchema(
                intent=IntentType.GREETING,
                semantic_query="",
                metadata_filters={},
                needs_clarification=False,
                clarification_question=None,
                has_conflict=False,
                conflict_reason=None,
            )

        if self._semantic_cache:
            cache_key = hashlib.sha256(
                f"extract:{normalized}:{json.dumps(last_filters or {}, sort_keys=True)}".encode() ).hexdigest()
            log_message( LG.LLM, f"🔑 [DEBUG] Cache Key: {cache_key[:16]}...", LogLevel.DEBUG )          # فقط ۱۶ کاراکتر اول
            cached = await self._semantic_cache.get( cache_key )
            if cached:
                log_message( LG.LLM, "⚡ Extract Cache Hit | بدون فراخوانی LLM", LogLevel.DEBUG )
                return LLMExtractSchema.model_validate( cached )
            else:
                log_message( LG.LLM, "❌ Cache Miss | ادامه با فراخوانی LLM", LogLevel.DEBUG )

        # ‫۲. ساخت Context پویا
        context_vars = {
            "query": normalized,
            "history": json.dumps( history or [], ensure_ascii=False ),
            "last_filters": json.dumps( last_filters or {}, ensure_ascii=False ),
            "last_products": json.dumps( last_products or [], ensure_ascii=False ),
            "domain_schema": self._domain_schema_str,
        }

        templates = self._config.prompts.get( "templates" )
        if isinstance( templates, dict ):
            template_str = templates.get( "extract", "" )
        else:
            template_str = ""

        user_prompt = Template( template_str ).safe_substitute( context_vars )
        system_prompt = str( self._config.prompts.get( "system_extract", "" ) )
        messages: list[ ChatCompletionMessageParam ] = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            },
        ]

        # ‫۳. فراخوانی LLM (Groq → Gemini Fallback)
        raw_json = ""
        token_usage = {}

        if self._settings.LLM_PRIMARY_PROVIDER.lower() == "gemini":          # 🔧 تعیین ترتیب ارائه‌دهندگان بر اساس تنظیمات
            providers = [ ( "gemini", self._gemini ), ( "groq", self._groq ) ]
        else:
            providers = [ ( "groq", self._groq ), ( "gemini", self._gemini ) ]

        for provider_name, provider_client in providers:
            try:
                log_message( LG.LLM, f"📡 ارسال درخواست به {provider_name.capitalize()}...", LogLevel.DEBUG )
                raw_json, token_usage = await provider_client.chat_json( cast( list, messages ) )
                log_message( LG.LLM,
                             f"✅ پاسخ از {provider_name.capitalize()} دریافت شد | TotalUsage: {token_usage.get('total_tokens', 0)}",
                             LogLevel.DEBUG )
                break
            except Exception as exc:
                log_message( LG.LLM, f"⚠️ {provider_name.capitalize()} ناموفق: {exc}", LogLevel.WARNING )
        else:
            log_message( LG.LLM, "❌ هر دو سرویس LLM ناموفق بودند", LogLevel.ERROR )
            raise RuntimeError( "هر دو سرویس LLM ناموفق بودند" )

        # ‫ ۴. پارس و اعتبارسنجی سخت‌گیرانه Pydantic
        try:
            cleaned = raw_json.replace( "```json", "" ).replace( "```", "" ).strip()
            start, end = cleaned.find( "{" ), cleaned.rfind( "}" )
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[ start:end + 1 ]

            validated = self._extract_validator.validate_python( json.loads( cleaned ) )

            price_filter = validated.metadata_filters.get( "price" )
            if isinstance( price_filter, dict ):
                floor = price_filter.get( ">=" ) or price_filter.get( ">" )
                has_ceiling = "<=" in price_filter or "<" in price_filter
                if floor and not has_ceiling:
                    price_filter[ "<=" ] = int( float( floor ) * self._price_ceiling_multiplier )

                    log_message( LG.LLM, f"🔒 سقف قیمت هوشمند فعال شد: < {price_filter['<=']:,}", LogLevel.DEBUG )

            # 💾 ذخیره در کش پس از موفقیت
            if self._semantic_cache and not validated.needs_clarification and not validated.has_conflict:
                await self._semantic_cache.set( cache_key, validated.model_dump() )
                log_message( LG.LLM, f"💾 Extract Cache Set | Key: {cache_key[:8]}...", LogLevel.DEBUG )

            total_usage = token_usage.get( 'total_tokens', 0 )
            log_message( LG.LLM, f"📥 Extract کوئری: '{query[:80]}' | Intent: {validated.intent.value} | TotalUsage: {total_usage}",
                         LogLevel.DEBUG )
            log_message( LG.LLM, f"📥 Extract | User: '{query[:40]}' | Semantic: '{validated.semantic_query}'", LogLevel.DEBUG )

            return validated

        except Exception as exc:
            log_message( LG.LLM, f"❌ خطای اعتبارسنجی Extract: {exc}", LogLevel.ERROR )
            raise ValueError( "خروجی LLM ساختار JSON معتبر ندارد" ) from exc

    # ──────────────────────────────────────  فاز 2   ──────────────────────────────────────
    async def generate(
        self,
        session_id: str,
        user_query: str,
        intent: str,
        filters_str: str | None,
        products: list[ QdrantProductPayload ],
        applied_filters: MetadataFilters | None = None,
        user_budget: int | float | None = None,
        min_price: int | float = 0,
    ) -> dict[ str, object ]:
        """اجرای کامل پایپلاین تولید پاسخ
 
        Args:
            session_id: شناسه نشست فعال
            user_query: متن کوئری کاربر
            intent: نیت تشخیص‌داده‌شده
            filters_str: نمایش رشته‌ای فیلترهای اعمال‌شده برای تزریق به پرامپت
            products: لیست محصولات بازیابی‌شده
            applied_filters: فیلترهای متادیتای اعمال‌شده (برای ذخیره در حافظه)
            
        Returns:
            دیکشنری پاسخ اعتبارسنجی‌شده
        """

        # ‫۱. ثبت پیام کاربر در حافظه
        await self._memory.add_message( session_id, "user", user_query )

        # ‫۲. ساخت پرامپت پایه
        messages = self._prompt_engine.render(
            intent,
            filters_str or "بدون فیلتر خاص",
            products,
            refine_query=user_query,
            user_budget=str( int( user_budget ) ) if user_budget else "نامشخص",
            min_price=str( int( min_price ) ),
        )

        # ‫ تزریق تاریخچه مکالمه برای refine (و سایر intentها)
        history = await self._memory.get_history( session_id )
        if len( history ) > 1:
            #‫ ‫درج پیام‌های قبلی قبل از پیام فعلی (حفظ ساختار role/content)
            for msg in history[ :-1 ]:
                messages.insert( -1, msg )

            # ‫ جایگزینی placeholder در refine با کوئری واقعی
            if intent == "refine" and messages:
                last_msg = messages[ -1 ]
                content = last_msg.get( "content" )
                if isinstance( content, str ):          # ‫ گارد تایپ: فقط اگر content رشته باشه اجرا می‌شه
                    last_msg[ "content" ] = content.replace( "{refine_query_placeholder}", user_query )

        # ‫۳. ارسال به LLM (Groq → Gemini Fallback)
        raw_json = ""
        token_usage = {}
        model_used = "unknown"

        # 🔧 تعیین ترتیب ارائه‌دهندگان بر اساس تنظیمات
        if self._settings.LLM_PRIMARY_PROVIDER.lower() == "gemini":
            providers = [ ( "gemini", self._gemini ), ( "groq", self._groq ) ]
        else:
            providers = [ ( "groq", self._groq ), ( "gemini", self._gemini ) ]

        for provider_name, client in providers:
            try:
                log_message( LG.LLM, f"📡 ارسال درخواست Generate به {provider_name.capitalize()}...", LogLevel.DEBUG )
                raw_json, token_usage = await client.chat_json( cast( list, messages ) )
                model_used = client._model
                break          # موفقیت‌آمیز بود، از حلقه خارج شو

            except Exception as exc:
                log_message( LG.LLM, f"⚠️ {provider_name.capitalize()} در generate ناموفق بود: {exc} | انتقال به فال‌بک...",
                             LogLevel.WARNING )
        else:
            # اگر حلقه بدون break تمام شد، یعنی هر دو شکست خوردند
            log_message( LG.LLM, "❌ هر دو سرویس LLM در generate ناموفق بودند", LogLevel.ERROR )
            return self._fallback_response( user_query, products )

        # ‫۴. اعتبارسنجی JSON و ثبت پاسخ در حافظه
        try:
            # ‫ پاکسازی احتمالی مارک‌داون و استخراج ایمن بلاک JSON
            cleaned = raw_json.replace( "```json", "" ).replace( "```", "" ).strip()
            start_idx = cleaned.find( "{" )
            end_idx = cleaned.rfind( "}" )

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = cleaned[ start_idx:end_idx + 1 ]
            else:
                json_str = cleaned          # ‫اگر ساختار پیدا نشد، متن خام پاس داده می‌شه تا json.loads خطا بده و لاگ بشه

            log_message( LG.LLM, f"📥 کوئری: '{user_query[:80]}...' | Intent: {intent} | 🔍 پاسخ نهایی (۲۰۰ کاراکتر اول): {json_str}",
                         LogLevel.DEBUG )

            validated = self._validator.validate_python( json.loads( json_str ) )
            await self._memory.add_message( session_id, "assistant", validated.explanation, applied_filters=applied_filters or {} )
            result = validated.model_dump()
            result[ "meta" ] = {
                "token_usage": token_usage,
                "model_used": model_used
            }          #‫ اضافه کردن آمار توکن‌ها برای ذخیره در سطح بالاتر(query_log_service)
            return result
        except Exception as exc:
            log_message( LG.LLM, f"❌ خطای اعتبارسنجی JSON: {exc}", LogLevel.ERROR )
            return self._fallback_response( user_query, products )

    @staticmethod
    def _fallback_response( query: str, products: list[ QdrantProductPayload ] ) -> dict[ str, object ]:
        """ ‫پاسخ قطعی در صورت شکست کامل LLM"""
        titles = "، ".join( [ p.title[ :30 ] for p in products[ :2 ] ] )
        return {
            "product_ids": [ p.product_id for p in products[ :2 ] ],
            "explanation": f"بر اساس جستجوی شما برای '{query[:30]}...', این موارد پیشنهاد می‌شوند: {titles}.",
            "next_suggestion": "می‌توانید فیلترها را تغییر دهید یا برند خاصی را مشخص کنید."
        }

    def _is_greeting_fast( self, text: str ) -> bool:
        """‫تشخیص آنی احوال‌پرسی بدون فراخوانی LLM (Latency <۱ms)"""
        if not self._greeting_keywords:
            return False
        normalized = self._normalizer.normalize( text ).strip()
        tokens = set( normalized.split() )

        if len( tokens ) > 3:
            return False

        return bool( tokens & self._greeting_keywords )

    def _build_domain_schema( self ) -> str:
        """‫تولید داینامیک راهنمای اسکیما و نگاشت‌های کیفی از YAML"""
        parts = [ "⚙️ Available Filters & Types:" ]
        slots = self._config.slot_definitions

        for key, cfg in slots.items():
            s_type = cfg.get( "type", "scalar" )
            units = list( cfg.get( "units", {} ).keys() )          # type: ignore
            example = " (مثال: {'price': {'<=': 20000000}} ← فقط تومان، بدون unit)" if key == "price" else ""
            unit_str = f" (units: {', '.join(units)})" if units and key != "price" else ""
            parts.append( f"- {key}: {s_type}{example}{unit_str}" )

        aliases = self._config.brand_aliases
        if aliases:
            parts.append( "\n🏷️ Brand Aliases (همیشه نام کانونیکال را برگردان):" )
            for alias, canonical in aliases.items():
                parts.append( f"- '{alias}' → '{canonical}'" )

        qual = self._config.qualitative_mappings
        if qual:
            parts.append( "\n🔗 Qualitative Mappings:" )
            for k, v in qual.items():
                if isinstance( v, dict ):
                    parts.append( f"- {k}:" )
                    for value, terms in v.items():
                        if isinstance( terms, list ):
                            fa_terms = "، ".join( terms )
                            parts.append( f"  - {fa_terms} → {value}" )

        use_cases = self._config.use_case_rules
        if use_cases:
            parts.append( "\n🎯 Use-Case Rules (وقتی کاربر این کلمات را گفت، این فیلترها را اعمال کن):" )
            for use_case, rules in use_cases.items():
                parts.append( f"- '{use_case}' → {rules}" )

        return "\n".join( parts )
