"""‫اسکریپت تست همگام‌سازی کامل با قابلیت Resume"""
import asyncio
import signal
import sys

from src.config.logging_config import log_message, LogLevel, LG
from src.data.sync.digikala_sync import DigikalaSyncService

# ‫مدیریت graceful shutdown با Ctrl+C
shutdown_requested = False


def handle_shutdown( signum, frame ) -> None:
    global shutdown_requested
    log_message( LG.DATA_PROCESSING, "⚠️ درخواست توقف دریافت شد — تکمیل محصول جاری و خروج ایمن...", LogLevel.WARNING )
    shutdown_requested = True


signal.signal( signal.SIGINT, handle_shutdown )


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "🚀 شروع تست همگام‌سازی کامل (بدون محدودیت محصول)...", LogLevel.INFO )

    try:
        sync_service = DigikalaSyncService()

        # ‫اجرای سرویس با max_products=None (پردازش تا پایان)
        success_count = await sync_service.run( max_products=None, checkpoint_every=5 )

        log_message( LG.DATA_PROCESSING, f"✅ پایان همگام‌سازی | محصولات موفق: {success_count}", LogLevel.INFO )

    except KeyboardInterrupt:
        log_message( LG.DATA_PROCESSING, "🛑 اجرا توسط کاربر متوقف شد", LogLevel.INFO )
    except Exception as exc:
        log_message( LG.DATA_PROCESSING, f"❌ خطای غیرمنتظره: {type(exc).__name__} — {exc}", LogLevel.CRITICAL )
        # ‫نمایش traceback کامل برای دیباگ
        import traceback
        log_message( LG.DATA_PROCESSING, f"Traceback:\n{traceback.format_exc()}", LogLevel.ERROR )
        sys.exit( 1 )


if __name__ == "__main__":
    asyncio.run( main() )
