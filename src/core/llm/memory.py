"""‫مدیریت حافظه مکالمه (Conversation Memory)
‫مسئول: نگهداری تاریخچه چت به‌صورت Session-based با الگوی Sliding Window
"""
from __future__ import annotations

import uuid
from collections import deque
from threading import Lock
from typing import Deque

from src.config.logging_config import log_message, LogLevel, LG


class ConversationMemory:
    """‫کش حافظه مکالمه درون‌حافظه‌ای برای محیط‌های Stateless وب‌سرویس"""

    def __init__( self, max_turns: int = 3 ) -> None:
        self._sessions: dict[ str, Deque[ dict[ str, str ] ] ] = {}
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

    def add_message( self, session_id: str, role: str, content: str ) -> None:
        """‫افزودن پیام کاربر یا سیستم به تاریخچه نشست"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[ session_id ].append( { "role": role, "content": content } )

    def get_history( self, session_id: str ) -> list[ dict[ str, str ] ]:
        """‫دریافت تاریخچه مکالمه نشست فعال"""
        with self._lock:
            return list( self._sessions.get( session_id, [] ) )
