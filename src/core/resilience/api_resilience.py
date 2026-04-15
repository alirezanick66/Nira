"""‫لایهٔ تاب‌آوری برای درخواست‌های HTTP خارجی
‫مسئول: Retry هوشمند، Exponential Backoff + Jitter، مدیریت اتصال
"""
import asyncio
import random
from typing import Callable, Awaitable, TypeVar
from httpx import HTTPStatusError
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type

from src.config.logging_config import log_message, LogLevel, LG

T = TypeVar( "T" )


class ApiResilienceLayer:
    """‫مدیریت تاب‌آوری و تلاش مجدد درخواست‌های شبکه"""

    def __init__(
        self,
        max_retries: int = 3,
        min_delay: float = 1.0,
        max_delay: float = 8.0,
    ) -> None:
        self._max_retries = max_retries
        self._min_delay = min_delay
        self._max_delay = max_delay

    async def execute( self, func: Callable[..., Awaitable[ T ] ], *args: object, **kwargs: object ) -> T:
        """‫اجرای تابع با لایهٔ Retry خودکار و تاخیر تصادفی

        Args:
            func: تابع غیرهمزمان (مثلاً کلاینت.get)
            *args, **kwargs: آرگومان‌های تابع

        Returns:
            خروجی تابع

        Raises:
            HTTPStatusError: در صورت شکست پس از تمام تلاش‌ها
        """

        @retry(
            stop=stop_after_attempt( self._max_retries ),
            wait=wait_random_exponential( multiplier=1, min=self._min_delay, max=self._max_delay ),
            retry=retry_if_exception_type( HTTPStatusError ),
            reraise=True,
        )
        async def _protected_call() -> T:
            return await func( *args, **kwargs )

        try:
            return await _protected_call()
        except HTTPStatusError as exc:
            log_message( LG.API, f"شکست نهایی پس از {self._max_retries} تلاش: {exc.response.status_code}", LogLevel.ERROR )
            raise
