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
from src.core.llm.prompts import PromptEngine
from src.core.llm.schemas import LLMResponseSchema
from src.core.vector.qdrant_payload import QdrantProductPayload


class LLMOrchestrator:

    def __init__( self ) -> None:
        self._memory = ConversationMemory( max_turns=3 )
        self._groq = GroqClient()
        self._gemini = GeminiClient()
        self._validator = TypeAdapter( LLMResponseSchema )
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
        self._memory.add_message( session_id, "user", user_query )
        messages = PromptEngine.build( intent, filters_str, products )

        # ‫✅ اصلاح: تزریق صحیح تاریخچه به‌عنوان پیام‌های user/assistant
        history = self._memory.get_history( session_id )
        if len( history ) > 1:
            # درج پیام‌های قبلی قبل از پیام فعلی
            for msg in history[ :-1 ]:
                messages.insert( -1, cast( ChatCompletionMessageParam, msg ) )

        raw_json = ""
        try:
            log_message( LG.LLM, "📡 ارسال درخواست به Groq...", LogLevel.DEBUG )
            raw_json = await self._groq.chat_json( messages )
        except Exception as exc:
            log_message( LG.LLM, f"⚠️ Groq ناموفق: {exc}. انتقال به Gemini...", LogLevel.WARNING )
            try:
                log_message( LG.LLM, "📡 ارسال درخواست به Gemini...", LogLevel.DEBUG )
                raw_json = await self._gemini.chat_json( messages )
            except Exception as gem_exc:
                log_message( LG.LLM, f"❌ هر دو سرویس LLM ناموفق بودند: {gem_exc}", LogLevel.ERROR )
                return self._fallback_response( user_query, products )

        try:
            #‫ ✅ اصلاح: استخراج ایمن بلاک JSON با Regex به‌جای strip شکننده
            match = re.search( r'\{.*\}', raw_json, re.DOTALL )
            cleaned = match.group( 0 ) if match else raw_json.strip()
            log_message( LG.LLM, f"🔍 پاسخ خام LLM (۲۰۰ کاراکتر اول): {cleaned[:200]}", LogLevel.DEBUG )
            validated = self._validator.validate_python( json.loads( cleaned ) )
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
