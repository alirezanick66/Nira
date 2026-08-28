"""‫سرویس همگام‌سازی هوشمند با قابلیت Resume و مدیریت خطای لایه‌ای"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
import asyncio
from httpx import HTTPStatusError

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.data.fetchers.digikala_api import DigikalaAPIClient
from src.data.repositories.product_repository import ProductRepository
from src.data.sync.progress_tracker import ProgressTracker
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

    #────────────────────────────────────────── Public Methods ──────────────────────────────────────────
    async def run(
        self,
        max_products: int | None = None,
        checkpoint_every: int = 10,
        stop_event: asyncio.Event | None = None,
    ) -> int:
        """‫اجرای چرخهٔ همگام‌سازی با قابلیت ادامه از نقطهٔ توقف (Resume)

        Args:
            max_products: حداکثر تعداد محصولات برای پردازش    (اختیاری).
            checkpoint_every: فاصلهٔ ذخیره‌سازی چک‌پوینت‌ها بر اساس تعداد محصولات پردازش‌شده (پیش‌فرض 10).
            stop_event: رویداد توقف ایمن برای کنترل خارجی چرخه.

        Returns:
            تعداد محصولات با موفقیت پردازش‌شده.

        Raises:
            Exception: در صورت بروز خطای غیرمنتظره در سطح چرخه که توسط لایه‌های پایین‌تر مدیریت نشده باشد.
        """
        last_id, last_page = await self._tracker.load()
        log_message( LG.DATA_PROCESSING, f"شروع همگام‌سازی | ادامه از ID: {last_id} | صفحه: {last_page}", LogLevel.INFO )

        success_count: int = 0
        processed_count: int = 0
        current_id: int | None = last_id
        current_page: int = last_page
        last_saved_id: int | None = None          # ✅ ردیابی آخرین چک‌پوینت ثبت‌شده

        try:
            async with DigikalaAPIClient() as client:
                async for pid, page in client.stream_product_ids( start_page=current_page ):
                    if stop_event and stop_event.is_set():
                        break

                    if max_products is not None and processed_count >= max_products:
                        break

                    current_id, current_page = pid, page

                    if await self._process_product( client, pid ):
                        success_count += 1
                        processed_count += 1

                        if processed_count % checkpoint_every == 0 and current_id != last_saved_id:
                            await self._tracker.save( current_id, page=current_page )
                            last_saved_id = current_id
                            log_message( LG.DATA_PROCESSING, f"📦 چک‌پوینت ذخیره شد | ID: {current_id}", LogLevel.DEBUG )

        finally:
            # ✅ ذخیره نهایی فقط در صورتی که تغییر جدیدی نسبت به آخرین چک‌پوینت رخ داده باشد
            if current_id and current_id != last_saved_id:
                try:
                    await self._tracker.save( current_id, page=current_page )
                except Exception as exc:
                    log_message( LG.DATA_PROCESSING, f"⚠️ خطا در ذخیره چک‌پوینت: {exc}", LogLevel.WARNING )

        log_message( LG.DATA_PROCESSING, f"پایان همگام‌سازی | موفق: {success_count}", LogLevel.DEBUG )
        return success_count

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    async def _process_product( self, client: DigikalaAPIClient, product_id: int ) -> bool:
        """‫دریافت، اعتبارسنجی و ذخیرهٔ ایزولهٔ یک محصول"""
        try:
            detail = await client.fetch_product_detail( product_id )
            await self._repo.save_raw( product_id, detail.model_dump() )
            log_message( LG.DATA_PROCESSING, f"✅ محصول {product_id} ذخیره شد", LogLevel.INFO )
            return True
        except HTTPStatusError as exc:
            log_message( LG.DATA_PROCESSING, f"🚫 خطای HTTP برای محصول {product_id}: {exc.response.status_code}", LogLevel.ERROR )
            return False
        except Exception as exc:
            log_message( LG.DATA_PROCESSING, f"⚠️ خطا در پردازش محصول {product_id}: {exc}", LogLevel.WARNING )
            return False
