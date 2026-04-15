"""‫سرویس همگام‌سازی هوشمند با قابلیت Resume و مدیریت خطای لایه‌ای"""
import asyncio

from src.data.fetchers.digikala_api import DigikalaAPIClient
from src.data.repositories.product_repository import ProductRepository
from src.core.progress_tracker import ProgressTracker
from src.data.db.engine import DatabaseEngine
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class DigikalaSyncService:
    """‫هماهنگ‌کنندهٔ استخراج، ذخیره و ردیابی پیشرفت"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._db = DatabaseEngine()
        self._repo = ProductRepository( self._db )
        self._tracker = ProgressTracker( self._db )

    #───────────────────── private methods ─────────────────────
    async def _process_product( self, client: DigikalaAPIClient, product_id: int ) -> bool:
        """‫دریافت، اعتبارسنجی و ذخیرهٔ ایزولهٔ یک محصول"""
        try:
            detail = await client.fetch_product_detail( product_id )
            await self._repo.save_raw( product_id, detail.model_dump() )
            log_message( LG.DATA_PROCESSING, f"✅ محصول {product_id} ذخیره شد", LogLevel.DEBUG )
            return True
        except Exception as exc:
            log_message( LG.DATA_PROCESSING, f"⚠️ خطا در پردازش محصول {product_id}: {exc}", LogLevel.WARNING )
            return False

    #───────────────────── public methods ─────────────────────
    async def run( self, max_products: int | None = None, checkpoint_every: int = 5, stop_event: asyncio.Event | None = None ) -> int:
        """‫اجرای چرخهٔ همگام‌سازی با قابلیت Resume

        Args:
            max_products: حداکثر تعداد محصول برای پردازش در این اجرا
            checkpoint_every: ذخیرهٔ پیشرفت پس از هر N محصول موفق

        Returns:
            تعداد محصولات موفقیت‌آمیز پردازش‌شده
        """
        last_id, start_page = await self._tracker.load()
        log_message( LG.DATA_PROCESSING, f"شروع همگام‌سازی ID: {last_id} | صفحه: {start_page}", LogLevel.INFO )

        success_count = 0
        processed_count = 0
        last_processed_id = last_id
        try:
            async with DigikalaAPIClient() as client:
                async for pid in client.stream_product_ids( start_page=start_page, resume_from_id=last_id ):

                    # ✅ بررسی درخواست توقف (Ctrl+C)
                    if stop_event and stop_event.is_set():
                        log_message( LG.DATA_PROCESSING, "🛑 توقف درخواست شد — ذخیرهٔ چک‌پوینت نهایی...", LogLevel.INFO )
                        break

                    if max_products and processed_count >= max_products:
                        break

                    if await self._process_product( client, pid ):
                        success_count += 1
                        processed_count += 1
                        last_processed_id = pid

                        if processed_count % checkpoint_every == 0:
                            await self._tracker.save( last_processed_id, page=start_page )

                # ذخیرهٔ نهایی پیشرفت
                if last_processed_id:
                    await self._tracker.save( last_processed_id, page=start_page )
        finally:
            # ✅ ذخیرهٔ اجباری آخرین وضعیت پیش از خروج (حتی در صورت خطا یا Ctrl+C)
            if last_processed_id and last_processed_id != last_id:
                await self._tracker.save( last_processed_id, page=start_page )

        log_message( LG.DATA_PROCESSING, f"پایان همگام‌سازی | موفق: {success_count}/{max_products}", LogLevel.INFO )
        return success_count
