"""‫مدیریت حافظه مکالمه (Conversation Memory)
‫مسئول: نگهداری تاریخچه چت + فیلترهای اعمال‌شده به‌صورت Session-based با الگوی Sliding Window
"""
from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Deque

from src.config.logging_config import log_message, LogLevel, LG


@dataclass
class _Turn:
    """یک نوبت مکالمه شامل پیام و فیلترهای اعمال‌شده"""
    role: str
    content: str
    applied_filters: dict = field( default_factory=dict )


class ConversationMemory:
    """ ‫‫کش حافظه مکالمه درون‌حافظه‌ای برای محیط‌های Stateless وب‌سرویس

    علاوه بر متن پیام‌ها، فیلترهای متادیتای آخرین جستجوی موفق را نیز
   ‫ به‌ازای هر session نگه می‌دارد تا intent: refine بتواند از آن‌ها بهره ببرد.
    """

    def __init__( self, max_turns: int = 3 ) -> None:
        self._sessions: dict[ str, Deque[ _Turn ] ] = {}
        self._lock = Lock()
        self._max_turns = max_turns
        log_message( LG.LLM, "سرویس ConversationMemory راه‌اندازی شد", LogLevel.INFO )

    def get_or_create_session( self, session_id: str | None = None ) -> str:
        """‫بازگرداندن یا ایجاد شناسه نشست جدید"""
        if not session_id:
            session_id = str( uuid.uuid4() )
        with self._lock:
            self._sessions.setdefault( session_id, deque( maxlen=self._max_turns ) )
        return session_id

    def add_message(
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
        with self._lock:
            if session_id in self._sessions:
                self._sessions[ session_id ].append( _Turn(
                    role=role,
                    content=content,
                    applied_filters=applied_filters or {},
                ) )

    def get_history( self, session_id: str ) -> list[ dict[ str, str ] ]:
        """‫دریافت تاریخچه مکالمه نشست فعال (فقط role/content برای LLM)"""
        with self._lock:
            return [ { "role": t.role, "content": t.content } for t in self._sessions.get( session_id, [] ) ]

    def get_last_filters( self, session_id: str ) -> dict:
        """‫آخرین فیلترهای جستجوی موفق نشست را برمی‌گرداند

        برای استفاده در intent: refine جهت حفظ context جستجوی قبلی.

        Returns:
            دیکشنری فیلترها یا دیکشنری خالی اگر تاریخچه‌ای وجود نداشته باشد
        """
        with self._lock:
            turns = self._sessions.get( session_id, deque() )
            # جستجو از آخر به اول برای یافتن آخرین نوبت با فیلتر غیرخالی
            for turn in reversed( turns ):
                if turn.applied_filters:
                    return dict( turn.applied_filters )
            return {}
