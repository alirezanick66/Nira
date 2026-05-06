"""استخراج‌گر Intent و Entity مبتنی بر LLM
مسئول: نرمال‌سازی متن با normalizer.py و number_converter.py، سپس استخراج ساختاریافته
نیت و فیلترها از طریق LLM (Groq اول، Gemini به‌عنوان fallback).
"""
#─────────────────────── Imports ───────────────────────────
from __future__ import annotations

import json
import unicodedata
from typing import cast

from groq.types.chat import ChatCompletionMessageParam

#─────────────────────── Local Imports ───────────────────────────
from src.config.domain_loader import DomainConfigLoader
from src.config.logging_config import log_message, LogLevel, LG
from src.core.llm.clients import GeminiClient, GroqClient
from src.core.llm.memory import ConversationMemory
from src.core.nlu.normalizer import PersianNormalizer
from src.core.nlu.schemas import MetadataFilters, NLUFilterQuery

_DEFAULT_GREETING = "سلام! چطور می‌تونم کمکتون کنم؟"

_SYSTEM_PROMPT = """تو یک سیستم استخراج اطلاعات ساختاریافته از متن فارسی هستی.
وظیفه‌ات تشخیص نیت کاربر و استخراج فیلترهای جستجو از کوئری است.
خروجی باید یک JSON معتبر بدون هیچ متن اضافه‌ای با این ساختار دقیق باشد:

{
  "intent": "search|refine|greeting|compare",
  "semantic_query": "متن تمیز برای جستجوی برداری",
  "metadata_filters": {},
  "is_greeting": false,
  "sort_directive": null
}

── تعریف intent‌ها ──
- search: جستجوی جدید یا اولین درخواست کاربر
- refine: اصلاح یا محدودکردن جستجوی قبلی (بر اساس تاریخچه مکالمه)
- compare: مقایسه بین محصولات
- greeting: احوال‌پرسی، تشکر، یا پیام غیرجستجویی

── فیلترهای پشتیبانی‌شده در metadata_filters ──
- price: {"<=": عدد} یا {">=": عدد} (به تومان)
- brand: "نام برند" (مقادیر مجاز: اپل، سامسونگ، شیائومی، هواوی، نوکیا، وان‌پلاس، آنر، موتورولا، سونی، ریلمی، پوکو)
- ram_gb: {">=": عدد} (گیگابایت)
- storage_gb: {">=": عدد} (گیگابایت)
- camera_quality: "good" یا "excellent"
- battery_quality: "good" یا "excellent"
- price_range: "budget" یا "mid" یا "premium" یا "flagship"
- tags: ["gaming", "photography", "lightweight"]

── قوانین فیلترسازی ──
- اعداد فارسی را به لاتین تبدیل کن (مثلاً ۳۰ میلیون → 30000000)
- "زیر X میلیون" → price: {"<=": X*1000000}
- "بالای X میلیون" → price: {">=": X*1000000}
- "X گیگ رم" یا "رم X گیگ" → ram_gb: {">=": X}
- "دوربین خوب" → camera_quality: "good"
- "دوربین عالی/حرفه‌ای/قوی" → camera_quality: "excellent"
- برندنرمالیزیشن: آیفون/ایفون/apple → اپل، samsung → سامسونگ، xiaomi → شیائومی
- "گیمینگ"/"بازی" → tags: ["gaming"]، ram_gb: {">=": 8}
- "عکاسی"/"فیلمبرداری" → camera_quality: "excellent"، tags: ["photography"]
- "سبک" → tags: ["lightweight"]

── قوانین sort_directive ──
- "ارزونتر/ارزان‌تر" بدون عدد صریح → sort_directive: {"key": "price", "order": "asc"}
- "گرونتر/گران‌تر" بدون عدد → sort_directive: {"key": "price", "order": "desc"}
- "رم بیشتر/بالاتر" بدون عدد صریح → sort_directive: {"key": "ram_gb", "order": "desc"}
- وقتی sort_directive تنظیم شد، metadata_filters را بدون تغییر بگذار (فیلترهای قبلی از حافظه ادغام می‌شوند)

── قوانین intent ──
- اگر کاربر در مکالمه قبلی جستجو کرده و الان چیزی اضافه یا تغییر می‌دهد → refine
  مثال: "سامسونگ باشه" بعد از جستجوی قبلی → refine با metadata_filters: {"brand": "سامسونگ"}
  مثال: "ارزونتر باشه" بعد از جستجو → refine با sort_directive
  مثال: "رم بیشتری داشته باشه" → refine با ram_gb یا sort_directive
- "مقایسه کن"، "کدوم بهتره"، "فرق چیه"، "vs" → compare
- "سلام"، "درود"، "ممنون"، احوال‌پرسی → greeting با is_greeting: true
- برای refine فقط تغییرات جدید را در metadata_filters بگذار (فیلترهای قبلی از حافظه بارگذاری می‌شوند)

── semantic_query ──
متن تمیز و مختصر برای جستجوی برداری، بدون کلمات قیمتی یا واحدها.
"""


class LLMNLUExtractor:
    """استخراج نیت و فیلترها با LLM به جای قوانین دستی

    این کلاس جایگزین NLUPipeline می‌شود و به جای TokenParser و ConflictResolver
    از یک مدل زبانی بزرگ برای استخراج ساختاریافته استفاده می‌کند.
    """

    def __init__(
        self,
        domain: str = "mobile",
        config_loader: DomainConfigLoader | None = None,
        memory: ConversationMemory | None = None,
    ) -> None:
        loader = config_loader or DomainConfigLoader()
        self._config = loader.load( domain )
        self._normalizer = PersianNormalizer()
        self._groq = GroqClient()
        self._gemini = GeminiClient()
        self._memory = memory or ConversationMemory()

        # دریافت پاسخ‌های سلام از کانفیگ دامنه
        intent_cfg = self._config.get( "intent_keywords", {} )
        greeting_cfg = intent_cfg.get( "greeting", {} ) if isinstance( intent_cfg, dict ) else {}
        self._greeting_responses: list[ str ] = (
            greeting_cfg.get( "greeting_responses", [ _DEFAULT_GREETING ] )
            if isinstance( greeting_cfg, dict ) else [ _DEFAULT_GREETING ]
        )
        log_message( LG.NLU, f"✅ LLMNLUExtractor برای دامنه '{domain}' آماده است", LogLevel.INFO )

    # ── رابط عمومی ───────────────────────────────────────────────────────────

    @property
    def greeting_responses( self ) -> list[ str ]:
        """پاسخ‌های احوال‌پرسی از کانفیگ دامنه"""
        return self._greeting_responses

    def get_domain_config( self ) -> dict:
        """دسترسی عمومی به کانفیگ دامنه (برای سازگاری با کد قبلی)"""
        return self._config

    async def extract( self, user_input: str, session_id: str ) -> NLUFilterQuery:
        """استخراج نیت و فیلترها از متن کاربر با استفاده از LLM

        Args:
            user_input: متن خام کوئری کاربر
            session_id: شناسه نشست برای دسترسی به تاریخچه مکالمه

        Returns:
            NLUFilterQuery آماده برای تزریق به لایه جستجو
        """
        # ۱. پیش‌پردازش با normalizer (نیمه‌فاصله، اعداد عربی، اعراب)
        normalized = self._preprocess( user_input )

        # ۲. دریافت تاریخچه مکالمه برای context-aware intent detection
        history = await self._memory.get_history( session_id )

        # ۳. ساخت پیام‌های LLM با تاریخچه
        messages = self._build_messages( normalized, history )

        # ۴. ارسال به LLM با fallback
        raw_json = await self._call_llm( cast( list[ ChatCompletionMessageParam ], messages ) )

        # ۵. پارس و اعتبارسنجی پاسخ JSON
        result = self._parse_response( raw_json, normalized )
        log_message(
            LG.NLU,
            f"✅ LLM NLU | Intent: {result.intent} | Filters: {result.metadata_filters} | Sort: {result.sort_directive}",
            LogLevel.DEBUG,
        )
        return result

    # ── متدهای خصوصی ─────────────────────────────────────────────────────────

    def _preprocess( self, text: str ) -> str:
        """نرمال‌سازی کامل متن ورودی (یکسان با NLUPipeline)"""
        normalized = self._normalizer.normalize( text )
        return unicodedata.normalize( "NFKC", normalized ).strip()

    def _build_messages(
        self,
        query: str,
        history: list[ dict[ str, str ] ],
    ) -> list[ dict[ str, str ] ]:
        """ساخت لیست پیام‌ها با تاریخچه مکالمه برای context-awareness"""
        messages: list[ dict[ str, str ] ] = [ { "role": "system", "content": _SYSTEM_PROMPT } ]
        for msg in history:
            messages.append( { "role": msg[ "role" ], "content": msg[ "content" ] } )
        messages.append( { "role": "user", "content": f"کوئری: {query}" } )
        return messages

    async def _call_llm( self, messages: list[ ChatCompletionMessageParam ] ) -> str:
        """ارسال به Groq، در صورت خطا fallback به Gemini"""
        try:
            return await self._groq.chat_json( messages )
        except Exception as exc:
            log_message( LG.NLU, f"⚠️ Groq ناموفق در NLU: {exc} — انتقال به Gemini", LogLevel.WARNING )
            return await self._gemini.chat_json( messages )

    def _parse_response( self, raw_json: str, fallback_query: str ) -> NLUFilterQuery:
        """پارس پاسخ JSON از LLM به NLUFilterQuery"""
        try:
            cleaned = raw_json.replace( "```json", "" ).replace( "```", "" ).strip()
            start = cleaned.find( "{" )
            end = cleaned.rfind( "}" )
            if start != -1 and end > start:
                cleaned = cleaned[ start:end + 1 ]
            data: dict = json.loads( cleaned )
        except Exception as exc:
            log_message(
                LG.NLU,
                f"❌ خطا در پارس JSON پاسخ LLM: {exc} | پاسخ خام: {raw_json[:200]}",
                LogLevel.ERROR,
            )
            return NLUFilterQuery(
                intent="search",
                semantic_query=fallback_query,
                metadata_filters={},
                is_greeting=False,
                warnings=[ str( exc ) ],
            )

        intent = str( data.get( "intent", "search" ) )
        semantic_query = str( data.get( "semantic_query", fallback_query ) ) or fallback_query
        raw_filters: dict = data.get( "metadata_filters" ) or {}
        is_greeting = bool( data.get( "is_greeting", False ) )
        sort_directive: dict[ str, str ] | None = data.get( "sort_directive" ) or None

        metadata_filters = self._normalize_filters( raw_filters )

        return NLUFilterQuery(
            intent=intent,
            semantic_query=semantic_query,
            metadata_filters=cast( MetadataFilters, metadata_filters ),
            is_greeting=is_greeting,
            warnings=[],
            sort_directive=sort_directive,
        )

    @staticmethod
    def _normalize_filters( filters: dict ) -> dict:
        """نرمال‌سازی مقادیر فیلترها — تبدیل اعداد (از جمله رشته‌های عددی) به float"""
        result: dict = {}
        for key, value in filters.items():
            if isinstance( value, dict ):
                normalized_inner: dict = {}
                for op, v in value.items():
                    if isinstance( v, ( int, float ) ):
                        normalized_inner[ op ] = float( v )
                    else:
                        try:
                            normalized_inner[ op ] = float( v )
                        except ( ValueError, TypeError ):
                            normalized_inner[ op ] = v
                result[ key ] = normalized_inner
            else:
                result[ key ] = value
        return result
