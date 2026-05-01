"""ارکستراتور اصلی LLM
مسئول: مدیریت چرخه کامل Memory → Prompt → Groq → Gemini(Fallback) → Validation
"""
#─────────────────────  Imports ─────────────────────
from __future__ import annotations
import re
import json
from pydantic import TypeAdapter
from typing import cast
from groq.types.chat import ChatCompletionMessageParam

#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.core.llm.clients import GroqClient, GeminiClient
from src.core.llm.memory import ConversationMemory
from src.core.llm.prompt_engine import PromptEngine
from src.core.llm.schemas import LLMResponseSchema
from src.core.vector.qdrant_payload import QdrantProductPayload


class LLMOrchestrator:

    def __init__( self, domain_config: dict ) -> None:
        self._memory = ConversationMemory( max_turns=3 )
        self._groq = GroqClient()
        self._gemini = GeminiClient()
        self._validator = TypeAdapter( LLMResponseSchema )
        self._prompt_engine = PromptEngine( domain_config )          # ✅ تزریق موتور پویا
        log_message( LG.LLM, "سرویس LLMOrchestrator آماده پذیرش درخواست است", LogLevel.INFO )

    async def generate(
        self,
        session_id: str,
        user_query: str,
        intent: str,
        filters_str: str | None,
        products: list[ QdrantProductPayload ],
    ) -> dict[ str, object ]:
        """اجرای کامل پایپلاین تولید پاسخ"""
        # ۱. ثبت پیام کاربر در حافظه
        self._memory.add_message( session_id, "user", user_query )

        # ۲. ساخت پرامپت پایه
        messages = self._prompt_engine.render( intent, filters_str or "بدون فیلتر خاص", products, refine_query=user_query )

        # ✅ تزریق تاریخچه مکالمه برای refine (و سایر intentها)
        history = self._memory.get_history( session_id )
        if len( history ) > 1:
            # درج پیام‌های قبلی قبل از پیام فعلی (حفظ ساختار role/content)
            for msg in history[ :-1 ]:
                messages.insert( -1, msg )

            # ✅ جایگزینی placeholder در refine با کوئری واقعی
            if intent == "refine" and messages:
                last_msg = messages[ -1 ]
                content = last_msg.get( "content" )
                if isinstance( content, str ):          # ✅ گارد تایپ: فقط اگر content رشته باشه اجرا می‌شه
                    last_msg[ "content" ] = content.replace( "{refine_query_placeholder}", user_query )

        # ۳. ارسال به LLM (Groq → Gemini Fallback)
        raw_json = ""
        groq_messages = cast( list[ ChatCompletionMessageParam ], messages )
        try:
            log_message( LG.LLM, "📡 ارسال درخواست به Groq...", LogLevel.DEBUG )
            raw_json = await self._groq.chat_json( groq_messages )
        except Exception as exc:
            log_message( LG.LLM, f"⚠️ Groq ناموفق: {exc}. انتقال به Gemini...", LogLevel.WARNING )
            try:
                log_message( LG.LLM, "📡 ارسال درخواست به Gemini...", LogLevel.DEBUG )
                raw_json = await self._gemini.chat_json( groq_messages )
            except Exception as gem_exc:
                log_message( LG.LLM, f"❌ هر دو سرویس LLM ناموفق بودند: {gem_exc}", LogLevel.ERROR )
                return self._fallback_response( user_query, products )

        # ۴. اعتبارسنجی JSON و ثبت پاسخ در حافظه
        try:
            # ✅ پاکسازی احتمالی مارک‌داون و استخراج ایمن بلاک JSON
            cleaned = raw_json.replace( "```json", "" ).replace( "```", "" ).strip()
            start_idx = cleaned.find( "{" )
            end_idx = cleaned.rfind( "}" )

            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = cleaned[ start_idx:end_idx + 1 ]
            else:
                json_str = cleaned          # اگر ساختار پیدا نشد، متن خام پاس داده می‌شه تا json.loads خطا بده و لاگ بشه

            log_message( LG.LLM, f"🔍 پاسخ خام LLM (۲۰۰ کاراکتر اول): {json_str[:200]}", LogLevel.DEBUG )

            validated = self._validator.validate_python( json.loads( json_str ) )
            self._memory.add_message( session_id, "assistant", validated.explanation )
            return validated.model_dump()
        except Exception as exc:
            log_message( LG.LLM, f"❌ خطای اعتبارسنجی JSON: {exc}", LogLevel.ERROR )
            return self._fallback_response( user_query, products )

    @staticmethod
    def _fallback_response( query: str, products: list[ QdrantProductPayload ] ) -> dict[ str, object ]:
        """پاسخ قطعی در صورت شکست کامل LLM"""
        titles = "، ".join( [ p.title[ :30 ] for p in products[ :2 ] ] )
        return {
            "product_ids": [ p.product_id for p in products[ :2 ] ],
            "explanation": f"بر اساس جستجوی شما برای '{query[:30]}...', این موارد پیشنهاد می‌شوند: {titles}.",
            "next_suggestion": "می‌توانید فیلترها را تغییر دهید یا برند خاصی را مشخص کنید."
        }
