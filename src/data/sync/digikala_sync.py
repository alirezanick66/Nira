"""‫سرویس همگام‌سازی استخراج داده از API دیجی‌کالا به PostgreSQL
‫این ماژول مسئول هماهنگی بین Fetch، Validate و Save است.
‫ویژگی‌ها:
‫- مدیریت همزمانی با Semaphore
‫- پردازش غیرهمزمان با حد حداکثر تعداد محصول
‫- مدیریت خطای مستقل برای هر محصول (تاب‌آوری بالا)
"""
import asyncio
from httpx import HTTPStatusError
from pydantic import ValidationError

from src.data.fetchers.digikala_api import DigikalaAPIClient
from src.data.repositories.product_repository import ProductRepository
from src.data.db.engine import DatabaseEngine
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class DigikalaSyncService:
    """‫هماهنگ‌کنندهٔ استخراج و ذخیرهٔ تدریجی محصولات"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._db_engine = DatabaseEngine()
        self._repo = ProductRepository( self._db_engine )
        self._semaphore = asyncio.Semaphore( self._settings.sync_concurrency )

    async def _process_product( self, client: DigikalaAPIClient, product_id: int ) -> bool:
        """‫دریافت، اعتبارسنجی و ذخیرهٔ یک محصول به صورت ایزوله"""
        async with self._semaphore:
            try:
                detail = await client.fetch_product_detail( product_id )
                await self._repo.save_raw( product_id, detail.model_dump() )
                log_message( LG.DATA_PROCESSING, f"محصول {product_id} با موفقیت ذخیره شد", LogLevel.DEBUG )
                return True
            except ( HTTPStatusError, ValidationError ) as exc:
                log_message( LG.DATA_PROCESSING, f"خطا در پردازش محصول {product_id}: {exc}", LogLevel.WARNING )
                return False
            except Exception as exc:
                log_message( LG.DATA_PROCESSING, f"خطای پیش‌بینی‌نشده محصول {product_id}: {exc}", LogLevel.ERROR )
                return False

    async def sync( self, max_products: int = 20 ) -> int:
        """‫اجرای چرخهٔ همگام‌سازی برای تعداد مشخصی محصول

        Args:
            max_products: حداکثر تعداد محصول برای پردازش (پیش‌فرض 20)

        Returns:
            تعداد محصولات موفقیت‌آمیز ذخیره‌شده
        """
        log_message( LG.DATA_PROCESSING, f"شروع همگام‌سازی | حد: {max_products} محصول", LogLevel.INFO )
        success_count = 0
        processed_count = 0

        async with DigikalaAPIClient() as client:
            async for product_id in client.stream_product_ids():
                if processed_count >= max_products:
                    break

                processed_count += 1
                if await self._process_product( client, product_id ):
                    success_count += 1

        log_message( LG.DATA_PROCESSING, f"پایان همگام‌سازی | موفق: {success_count}/{max_products}", LogLevel.INFO )
        return success_count
