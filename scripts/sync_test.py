"""‫اسکریپت تست همگام‌سازی اولیه داده‌ها"""
import asyncio
from src.data.sync.digikala_sync import DigikalaSyncService
from src.config.logging_config import log_message, LogLevel, LG


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "شروع تست همگام‌سازی ۲۰ محصول...", LogLevel.INFO )
    try:
        sync_service = DigikalaSyncService()
        success_count = await sync_service.sync( max_products=20 )
        log_message( LG.DATA_PROCESSING, f"تست با موفقیت پایان یافت | {success_count} محصول ذخیره شد", LogLevel.INFO )
    except Exception as exc:
        log_message( LG.DATA_PROCESSING, f"خطای غیرمنتظره در تست: {exc}", LogLevel.CRITICAL )


if __name__ == "__main__":
    asyncio.run( main() )
