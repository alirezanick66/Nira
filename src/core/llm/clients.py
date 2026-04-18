"""‫کلاینت‌های LLM با پشتیبانی از JSON Mode و مدیریت خطای Rate Limit
‫مسئول: ارتباط ایمن با Groq (Primary) و Gemini (Fallback)
"""
from __future__ import annotations

import time
from typing import Any

import groq
import google.genai as genai
from google.genai import types
from groq.types.chat import ChatCompletionMessageParam
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class _BaseLLMClient:
    """‫کلاس پایه مشترک برای مدیریت Retry و لاگ‌گذاری"""
    MAX_RETRIES = 2
    BACKOFF_FACTOR = 1.5

    @staticmethod
    def _retry_on_429( func: Any, *args: Any, **kwargs: Any ) -> Any:
        """‫اجرای مجدد هوشمند در صورت خطای 429 Too Many Requests (پلن رایگان)"""
        for attempt in range( _BaseLLMClient.MAX_RETRIES ):
            try:
                return func( *args, **kwargs )
            except Exception as exc:
                if "429" in str( exc ) and attempt < _BaseLLMClient.MAX_RETRIES - 1:
                    wait = _BaseLLMClient.BACKOFF_FACTOR ** attempt
                    log_message( LG.LLM, f"⏳ محدودیت نرخ API. تلاش مجدد پس از {wait:.1f}s...", LogLevel.WARNING )
                    time.sleep( wait )
                    continue
                raise
        return func( *args, **kwargs )


class GroqClient( _BaseLLMClient ):
    """‫کلاینت Groq با پشتیبانی از JSON Structured Output"""

    def __init__( self ) -> None:
        settings = get_settings()
        self._client = groq.Groq( api_key=settings.GROQ_API_KEY, timeout=15.0 )
        self._model = settings.GROQ_MODEL
        log_message( LG.LLM, f"کلاینت Groq آماده شد | مدل: {self._model}", LogLevel.INFO )

    def chat_json( self, messages: list[ ChatCompletionMessageParam ] ) -> str:
        """‫ارسال درخواست و دریافت پاسخ JSON-محور"""

        def _call():
            return self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=0.3,
                response_format={ "type": "json_object" },
            )

        response = self._retry_on_429( _call )
        content = response.choices[ 0 ].message.content
        if not content:
            raise ValueError( "پاسخ Groq خالی دریافت شد" )
        return content


class GeminiClient( _BaseLLMClient ):
    """‫کلاینت Gemini با پشتیبانی از JSON MIME Type"""

    def __init__( self ) -> None:
        settings = get_settings()
        self._client = genai.Client( api_key=settings.GEMINI_API_KEY )
        self._model = settings.GEMINI_MODEL
        log_message( LG.LLM, f"کلاینت Gemini آماده شد | مدل: {self._model}", LogLevel.INFO )

    def chat_json( self, messages: list[ ChatCompletionMessageParam ] ) -> str:
        """‫ارسال درخواست و دریافت پاسخ JSON-محور"""

        def _call():
            # جداسازی System Prompt از تاریخچه برای ارسال صحیح به Gemini
            system_text = next( ( m[ "content" ] for m in messages if m[ "role" ] == "system" ), None )
            user_messages = [ m for m in messages if m[ "role" ] != "system" ]

            config = types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                system_instruction=system_text,
            )
            return self._client.models.generate_content(
                model=self._model,
                contents=user_messages,
                config=config,
            )

        response = self._retry_on_429( _call )
        content = response.text
        if not content:
            raise ValueError( "پاسخ Gemini خالی دریافت شد" )
        return content
