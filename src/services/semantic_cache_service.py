#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import time
import asyncio
from typing import Any
#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.logging_config import log_message, LogLevel, LG


class AsyncTTLCache:
    """ کش درون‌حافظهٔ ایمن برای رویدادها با پشتیبانی از TTL و قفل Async """

    def __init__( self, ttl_seconds: int = 7200 ) -> None:
        self._store: dict[ str, tuple[ Any, float ] ] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        log_message( LG.LLM, f"⚡ سرویس SemanticCache راه‌اندازی شد | TTL: {ttl_seconds}s", LogLevel.INFO )


#────────────────────────────────────────── Public methods ──────────────────────────────────────────

    async def get( self, key: str ) -> Any | None:
        """ دریافت مقدار از کش در صورت عدم انقضا """
        async with self._lock:
            entry = self._store.get( key )
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[ key ]
                return None
            return value

    async def set( self, key: str, value: Any ) -> None:
        """ ذخیره مقدار با محاسبهٔ زمان انقضا """
        expires_at = time.monotonic() + self._ttl
        async with self._lock:
            self._store[ key ] = ( value, expires_at )

    async def clear( self ) -> None:
        """ پاک‌سازی کامل کش (برای Invalidation آینده یا تست) """
        async with self._lock:
            self._store.clear()

    @property
    def size( self ) -> int:
        return len( self._store )
