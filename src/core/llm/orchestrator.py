"""ارکستراتور اصلی LLM
‫مسئول: مدیریت چرخه کامل Memory → Prompt → Groq → Gemini(Fallback) → Validation
"""
#──────────────────────────────────────────  Imports ──────────────────────────────────────────
from __future__ import annotations
import json
from pydantic import TypeAdapter
from typing import cast
from string import Template
from groq.types.chat import ChatCompletionMessageParam

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.domain_loader import DomainConfig
from src.config.logging_config import log_message, LogLevel, LG
from src.core.llm.clients import GroqClient, GeminiClient
from src.core.llm.memory import ConversationMemory
from src.core.llm.prompt_engine import PromptEngine
from src.core.llm.schemas import LLMResponseSchema, LLMExtractSchema, IntentType, MetadataFilters
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.utils.normalizer import PersianNormalizer


class LLMOrchestrator:

    def __init__( self, domain_config: DomainConfig ) -> None:
        self._config = domain_config
        self._memory = ConversationMemory( max_turns=3 )
        self._groq = GroqClient()
        self._gemini = GeminiClient()
        self._validator = TypeAdapter( LLMResponseSchema )
        self._extract_validator = TypeAdapter( LLMExtractSchema )
        self._prompt_engine = PromptEngine( domain_config )
        self._normalizer = PersianNormalizer()

        # ‫کش کلمات کلیدی برای Fast-Path Greeting
        self._greeting_keywords = frozenset( self._config.intent_keywords.get( "greeting", {} ).get( "keywords_fast", [] ) )

        # ✅ محاسبهٔ یک‌بارهٔ Domain Schema در استارت‌آپ (جلوگیری از سربار تکراری)
        self._domain_schema_str = self._build_domain_schema()
        log_message( LG.LLM, "سرویس LLMOrchestrator آماده پذیرش درخواست است", LogLevel.INFO )

    # ═══════════════════════════════════════════════════════════════════════════
    # 🟢 فاز ۲: متدهای جدید استخراج نیت/فیلتر + چک سریع
    # ═══════════════════════════════════════════════════════════════════════════

    async def generate(
        self,
        session_id: str,
        user_query: str,
        intent: str,
        filters_str: str | None,
        products: list[ QdrantProductPayload ],
        applied_filters: dict | None = None,
    ) -> dict[ str, object ]:
        """اجرای کامل پایپلاین تولید پاسخ
 
        Args:
            session_id: شناسه نشست فعال
            user_query: متن کوئری کاربر
            intent: نیت تشخیص‌داده‌شده
            filters_str: نمایش رشته‌ای فیلترهای اعمال‌شده برای تزریق به پرامپت
            products: لیست محصولات بازیابی‌شده
            applied_filters: فیلترهای متادیتای اعمال‌شده (برای ذخیره در حافظه)
        """
        # ‫۱. ثبت پیام کاربر در حافظه
        await self._memory.add_message( session_id, "user", user_query )

        # ‫۲. ساخت پرامپت پایه
        messages = self._prompt_engine.render( intent, filters_str or "بدون فیلتر خاص", products, refine_query=user_query )

        # ‫ تزریق تاریخچه مکالمه برای refine (و سایر intentها)
        history = await self._memory.get_history( session_id )
        if len( history ) > 1:
            # ‫درج پیام‌های قبلی قبل از پیام فعلی (حفظ ساختار role/content)
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
        groq_messages = cast( list[ ChatCompletionMessageParam ], messages )
        try:
            log_message( LG.LLM, "📡 ارسال درخواست به Groq...", LogLevel.DEBUG )
            raw_json, token_usage = await self._groq.chat_json( cast( list, messages ) )
        except Exception as exc:
            log_message( LG.LLM, f"⚠️ Groq ناموفق: {exc}. انتقال به Gemini...", LogLevel.WARNING )
            try:
                log_message( LG.LLM, "📡 ارسال درخواست به Gemini...", LogLevel.DEBUG )
                raw_json, token_usage = await self._gemini.chat_json( cast( list, messages ) )
            except Exception as gem_exc:
                log_message( LG.LLM, f"❌ هر دو سرویس LLM ناموفق بودند: {gem_exc}", LogLevel.ERROR )
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
            return validated.model_dump()
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
        """تشخیص آنی احوال‌پرسی بدون فراخوانی LLM (Latency <۱ms)"""
        if not self._greeting_keywords:
            return False
        normalized = self._normalizer.normalize( text ).strip()
        tokens = set( normalized.split() )
        return bool( tokens & self._greeting_keywords )

    def _build_domain_schema( self ) -> str:
        """تولید داینامیک راهنمای اسکیما و نگاشت‌های کیفی از YAML"""
        parts = [ "⚙️ Available Filters & Types:" ]
        slots = self._config.slot_definitions

        for key, cfg in slots.items():
            s_type = cfg.get( "type", "scalar" )
            units = list( cfg.get( "units", {} ).keys() )

            # ✅ افزودن مثال‌های صریح برای جلوگیری از Hallucination کلید unit
            example = " (مثال: {'price': {'<=': 20000000}} ← فقط تومان، بدون unit)" if key == "price" else ""
            unit_str = f" (units: {', '.join(units)})" if units and key != "price" else ""

            parts.append( f"- {key}: {s_type}{example}{unit_str}" )

        qual = self._config.qualitative_mappings
        if qual:
            parts.append( "\n🔗 Qualitative Mappings:" )
            for k, v in qual.items():
                if isinstance( v, dict ):
                    parts.append( f"- {k}: {list(v.keys())}" )

        return "\n".join( parts )

    async def extract( self,
                       query: str,
                       session_id: str,
                       last_filters: MetadataFilters | None = None,
                       last_products: list[ str ] | None = None,
                       history: list[ dict[ str, str ] ] | None = None ) -> LLMExtractSchema:
        """استخراج نیت، فیلترها و کوئری معنایی با اعتبارسنجی سخت‌گیرانه"""
        normalized = self._normalizer.normalize( query )

        # ۱. Fast-Path Greeting Check
        if self._is_greeting_fast( normalized ):
            log_message( LG.LLM, "👋 Greeting شناسایی شد (Fast-Path) | بدون فراخوانی LLM", LogLevel.DEBUG )
            return LLMExtractSchema( intent=IntentType.GENERAL_CHAT,
                                     semantic_query="",
                                     metadata_filters={},
                                     needs_clarification=False,
                                     clarification_question=None,
                                     has_conflict=False,
                                     conflict_reason=None )

        # ۲. ساخت Context پویا
        context_vars = {
            "query": normalized,
            "history": json.dumps( history or [], ensure_ascii=False ),
            "last_filters": json.dumps( last_filters or {}, ensure_ascii=False ),
            "last_products": json.dumps( last_products or [], ensure_ascii=False ),
            "domain_schema": self._domain_schema_str,          # ✅ فقط خواندن از کش
        }
        prompts = self._config.prompts
        templates = prompts.get( "templates" ) or {}
        template_str = templates.get( "extract", "" )

        if not template_str:
            raise RuntimeError( "⛔ تمپلیت extract در base.yaml تعریف نشده یا indentation آن شکسته است." )

        user_prompt = Template( template_str ).safe_substitute( context_vars )
        system_prompt = self._config.prompts.get( "system_extract", "" )
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

        # ۳. فراخوانی LLM (Groq → Gemini Fallback)
        raw_json = ""
        try:
            raw_json, token_usage = await self._groq.chat_json( cast( list, messages ) )
        except Exception as exc:
            log_message( LG.LLM, f"⚠️ Groq failed in extract: {exc} | Switching to Gemini...", LogLevel.WARNING )
            try:
                raw_json, token_usage = await self._groq.chat_json( cast( list, messages ) )
            except Exception as gem_exc:
                log_message( LG.LLM, f"❌ هر دو سرویس LLM در extract ناموفق بودند: {gem_exc}", LogLevel.ERROR )
                raise RuntimeError( "سرویس استخراج LLM در دسترس نیست" ) from gem_exc

        # ۴. پارس و اعتبارسنجی سخت‌گیرانه Pydantic
        try:
            cleaned = raw_json.replace( "```json", "" ).replace( "```", "" ).strip()
            start, end = cleaned.find( "{" ), cleaned.rfind( "}" )
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[ start:end + 1 ]

            validated = self._extract_validator.validate_python( json.loads( cleaned ) )
            log_message( LG.LLM, f"📥 Extract کوئری: '{query[:80]} |  {validated}", LogLevel.DEBUG )
            return validated

        except Exception as exc:
            log_message( LG.LLM, f"❌ خطای اعتبارسنجی Extract: {exc}", LogLevel.ERROR )
            raise ValueError( "خروجی LLM ساختار JSON معتبر ندارد" ) from exc
