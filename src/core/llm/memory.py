"""‫مدیریت حافظه مکالمه (Conversation Memory)
‫مسئول: نگهداری تاریخچه چت، فیلترهای اعمال‌شده، و ادغام فیلترهای refine
"""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
import asyncio
from typing import Deque

from src.config.logging_config import log_message, LogLevel, LG


@dataclass
class _Turn:
    """یک نوبت مکالمه شامل پیام و فیلترهای اعمال‌شده"""
    role: str
    content: str
    applied_filters: dict = field( default_factory=dict )


class ConversationMemory:
    """‫کش حافظه مکالمه درون‌حافظه‌ای برای محیط‌های Stateless وب‌سرویس

    علاوه بر متن پیام‌ها، فیلترهای متادیتای آخرین جستجوی موفق را نیز
    به‌ازای هر session نگه می‌دارد تا intent: refine بتواند از آن‌ها بهره ببرد.
    """

    def __init__( self, max_turns: int = 3 ) -> None:
        self._sessions: dict[ str, Deque[ _Turn ] ] = {}
        self._lock = asyncio.Lock()
        self._max_turns = max_turns
        log_message( LG.LLM, "سرویس ConversationMemory راه‌اندازی شد", LogLevel.INFO )

    async def get_or_create_session( self, session_id: str | None = None ) -> str:
        """‫بازگرداندن یا ایجاد شناسه نشست جدید"""
        if not session_id:
            session_id = str( uuid.uuid4() )
        async with self._lock:
            self._sessions.setdefault( session_id, deque( maxlen=self._max_turns ) )
        return session_id

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        applied_filters: dict | None = None,
    ) -> None:
        """‫افزودن پیام کاربر یا سیستم به تاریخچه نشست

        Args:
            session_id: شناسه نشست فعال
            role: نقش فرستنده (user | assistant)
            content: متن پیام
            applied_filters: فیلترهای متادیتای اعمال‌شده در این نوبت (اختیاری)
        """
        async with self._lock:
            self._sessions.setdefault( session_id, deque( maxlen=self._max_turns ) )
            self._sessions[ session_id ].append( _Turn( role=role, content=content, applied_filters=applied_filters or {} ) )

    async def get_history( self, session_id: str ) -> list[ dict[ str, str ] ]:
        """‫دریافت تاریخچه مکالمه نشست فعال (فقط role/content برای LLM)"""
        async with self._lock:
            return [ { "role": t.role, "content": t.content } for t in self._sessions.get( session_id, [] ) ]

    async def get_last_filters( self, session_id: str ) -> dict:
        """‫آخرین فیلترهای جستجوی موفق نشست را برمی‌گرداند

        Returns:
            دیکشنری فیلترها یا دیکشنری خالی اگر تاریخچه‌ای وجود نداشته باشد
        """
        async with self._lock:
            turns = self._sessions.get( session_id, deque() )
            for turn in reversed( turns ):
                if turn.applied_filters:
                    return dict( turn.applied_filters )
            return {}

    async def merge_refine_filters(
        self,
        intent: str,
        new_filters: dict,
        session_id: str,
        sort_directive: dict | None = None,
    ) -> dict:
        """‫فیلترهای جدید را با فیلترهای session قبلی ادغام می‌کند

        منطق ادغام:
        - اگر intent برابر refine نبود → فیلترهای جدید بدون تغییر برگشت می‌دهد
        - اگر intent برابر refine بود:
            ۱. فیلترهای session قبلی به‌عنوان پایه استفاده می‌شوند
            ۲. فیلترهای جدید روی فیلترهای قبلی override می‌کنند
            ۳. فیلترهایی مثل brand که در کوئری جدید نیستند، حفظ می‌شوند

        Args:
            intent: نیت تشخیص‌داده‌شده توسط NLU
            new_filters: فیلترهای استخراج‌شده از کوئری جدید
            session_id: شناسه نشست برای دسترسی به حافظه
            sort_directive: دایرکتیو مرتب‌سازی برای حذف فیلترهای کیفی ناسازگار (اختیاری)

        Returns:
            دیکشنری فیلترهای ادغام‌شده
        """
        if intent != "refine":
            return new_filters

        last_filters = await self.get_last_filters( session_id )

        if not last_filters:
            log_message( LG.LLM, "⚠️ refine: فیلتر قبلی در حافظه یافت نشد، فیلترهای جدید استفاده می‌شوند", LogLevel.WARNING )
            return new_filters

        merged = { **last_filters, **new_filters }
        if ( sort_directive and sort_directive.get( "key" ) == "price" and "price" not in merged
             and "price_range" in merged ):
            merged.pop( "price_range", None )
        log_message( LG.LLM, f"🔀 refine merge | قبلی: {last_filters} | جدید: {new_filters} | نهایی: {merged}", LogLevel.DEBUG )
        return merged
