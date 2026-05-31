""" ‫کلاینت‌های LLM با پشتیبانی از JSON Mode و مدیریت خطای Rate Limit
مسئول: ارتباط ایمن ‫با Groq (Primary) و Gemini (Fallback)
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import asyncio
from typing import Any, Awaitable, Callable, TypeVar, cast
import groq
import google.genai as genai
from google.genai import types
from groq.types.chat import ChatCompletionMessageParam

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class _BaseLLMClient:
    """ ‫کلاس پایه مشترک برای مدیریت Retry و لاگ‌گذاری کلاینت‌های LLM"""
    MAX_RETRIES: int = 2
    BACKOFF_FACTOR: float = 1.5

    _T = TypeVar( "_T" )

    @staticmethod
    async def _retry_on_rate_limit( func: Callable[..., Awaitable[ _T ] ], *args: object, **kwargs: Any ) -> _T:
        """اجرای مجدد هوشمند در صورت خطای 429 Too Many Requests"""
        timeout = get_settings().GROQ_TIMEOUT_SEC
        for attempt in range( _BaseLLMClient.MAX_RETRIES ):
            try:
                async with asyncio.timeout( timeout ):
                    return await func( *args, **kwargs )

            except asyncio.TimeoutError as exc:
                log_message( LG.LLM, f"⏱️ LLM timeout بعد از {timeout}s (تلاش {attempt + 1})", LogLevel.WARNING )
                if attempt < _BaseLLMClient.MAX_RETRIES - 1:
                    # Retry فوری بدون delay برای timeout (برای جلوگیری از client timeout)
                    continue
                raise RuntimeError( f"LLM request timed out after {timeout}s" ) from exc
            except Exception as exc:
                is_rate_limit = ( isinstance( exc, groq.RateLimitError ) or getattr( exc, "status_code", None ) == 429
                                  or getattr( exc, "code", None ) == 429 )
                if is_rate_limit and attempt < _BaseLLMClient.MAX_RETRIES - 1:
                    wait: float = _BaseLLMClient.BACKOFF_FACTOR ** attempt
                    log_message( LG.LLM, f"⏳ محدودیت نرخ API. تلاش مجدد پس از {wait:.1f}s...", LogLevel.WARNING )
                    await asyncio.sleep( wait )
                    continue
                raise
        # Final attempt
        async with asyncio.timeout( timeout ):
            return await func( *args, **kwargs )


class GroqClient( _BaseLLMClient ):
    """کلاینت Groq با پشتیبانی از JSON Structured Output"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._client = groq.AsyncGroq(
            api_key=self._settings.GROQ_API_KEY,
            timeout=self._settings.GROQ_TIMEOUT_SEC,
        )
        self._model = self._settings.GROQ_MODEL
        log_message( LG.LLM, f"کلاینت Groq آماده شد | مدل: {self._model}", LogLevel.INFO )

    async def chat_json( self, messages: list[ ChatCompletionMessageParam ] ) -> tuple[ str, dict[ str, int ] ]:
        """ ‫ارسال درخواست و دریافت پاسخ JSON-محور از Groq"""

        async def _call() -> tuple[ str, dict[ str, int ] ]:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._settings.LLM_TEMPERATURE,
                response_format={ "type": "json_object" },
            )
            content = response.choices[ 0 ].message.content
            if not content:
                raise ValueError( "پاسخ Groq خالی دریافت شد" )
            usage = response.usage
            if not usage:
                raise ValueError( "اطلاعات استفاده (usage) در پاسخ Groq موجود نیست" )
            return content, {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            }

        return await self._retry_on_rate_limit( _call )


class GeminiClient( _BaseLLMClient ):
    """کلاینت Gemini با پشتیبانی از JSON MIME Type"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._client = genai.Client( api_key=self._settings.GEMINI_API_KEY )
        self._model = self._settings.GEMINI_MODEL
        log_message( LG.LLM, f"کلاینت Gemini آماده شد | مدل: {self._model}", LogLevel.INFO )

    async def chat_json( self, messages: list[ ChatCompletionMessageParam ] ) -> tuple[ str, dict[ str, int ] ]:
        """ ‫ارسال درخواست و دریافت پاسخ JSON-محور از Gemini"""

        async def _call() -> tuple[ str, dict[ str, int ] ]:
            system_text = next( ( m.get( "content" ) for m in messages if m.get( "role" ) == "system" ), None )
            user_contents = [
                str( content ) for m in messages if m.get( "role" ) in ( "user", "assistant" )
                if ( content := m.get( "content" ) ) is not None
            ]

            config = types.GenerateContentConfig(
                temperature=self._settings.LLM_TEMPERATURE,
                response_mime_type="application/json",
                system_instruction=system_text,
            )
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=user_contents[ 0 ] if len( user_contents ) == 1 else user_contents,
                config=config,
            )
            if not response.text:
                raise ValueError( "پاسخ Gemini خالی دریافت شد" )

            meta = response.usage_metadata
            if not meta:
                raise ValueError( "اطلاعات استفاده (usage_metadata) در پاسخ Gemini موجود نیست" )
            return response.text, {
                "prompt_tokens": meta.prompt_token_count or 0,
                "completion_tokens": meta.candidates_token_count or 0,
                "total_tokens": meta.total_token_count or 0,
            }

        return await self._retry_on_rate_limit( _call )
