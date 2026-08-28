"""‫اسکریپت تست همگام‌سازی کامل با قابلیت Resume"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
import asyncio
import signal
import sys

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.data.sync.digikala_sync import DigikalaSyncService


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "🚀 شروع همگام‌سازی (پشتیبانی از Resume)...", LogLevel.INFO )

    stop_event = asyncio.Event()

    def _handle_shutdown( signum: int, frame: object ) -> None:
        if not stop_event.is_set():
            log_message( LG.DATA_PROCESSING, "⚠️ دریافت سیگنال توقف — ذخیرهٔ پیشرفت و خروج ایمن...", LogLevel.WARNING )
            stop_event.set()
        else:
            log_message( LG.DATA_PROCESSING, "⛔ خروج اجباری درخواست شد...", LogLevel.CRITICAL )
            sys.exit( 1 )

    # ‫ثبت هندلر سیگنال سازگار با ویندوز و لینوکس
    try:
        signal.signal( signal.SIGINT, _handle_shutdown )
        signal.signal( signal.SIGTERM, _handle_shutdown )
    except ( OSError, NotImplementedError ):
        pass          # ‫در محیط‌های محدود سیگنال، از fallback استفاده می‌شود

    try:
        sync_service = DigikalaSyncService()
        success_count = await sync_service.run(
            max_products=None,          # ‫تعداد محصول برای تست (قابل تنظیم)
            stop_event=stop_event,
        )
        log_message( LG.DATA_PROCESSING, f"✅ پایان همگام‌سازی | محصولات موفق: {success_count}", LogLevel.INFO )

    except KeyboardInterrupt:
        _handle_shutdown( signal.SIGINT, None )
        await asyncio.sleep( 0.5 )          # ‫فرصت کوتاه برای اجرای finally و commit نهایی
    except Exception as exc:
        log_message( LG.DATA_PROCESSING, f"❌ خطای غیرمنتظره: {type(exc).__name__} — {exc}", LogLevel.CRITICAL )
        import traceback
        log_message( LG.DATA_PROCESSING, f"Traceback:\n{traceback.format_exc()}", LogLevel.ERROR )
        sys.exit( 1 )


if __name__ == "__main__":
    asyncio.run( main() )
