"""‫کلاینت غیرهمزمان استخراج داده از API دیجی‌کالا
‫این ماژول مسئول دریافت لیست محصولات و جزئیات هر محصول با اعتبارسنجی Pydantic است.
‫ویژگی‌ها:
‫- مدیریت چرخه حیات با Async Context Manager
‫- Rate Limiting داخلی (Semaphore + Delay)
‫- Retry خودکار برای خطاهای شبکه با Tenacity
‫- اعتبارسنجی صریح خروجی API توسط مدل‌های Pydantic
"""
#───────────────────── Imports ─────────────────────
import asyncio
from typing import AsyncIterator, Self
from httpx import AsyncClient, HTTPStatusError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import ValidationError

#───────────────────── Imports داخلی پروژه─────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.data.models.api.api_responses import ( DigikaiaProductListResponse, DigikaiaProductDetailResponse )


class DigikalaAPIClient:
    """‫کلاینت امن و Rate-Limited برای ارتباط با API دیجی‌کالا"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._client: AsyncClient | None = None
        self._semaphore = asyncio.Semaphore( 5 )

        # ‫خواندن تنظیمات از Settings یا Environment Variables (گزینه ۲ تولید)
        self._base_url = self._settings.DIGIKALA_BASE_URL
        self._headers = { "Accept": "application/json", "User-Agent": "NiraBot/1.0 (Internal-Scraping)" }

    async def __aenter__( self ) -> Self:
        """‫راه‌اندازی کلاینت HTTP و بازگرداندن نمونه جهت استفاده در async with"""
        self._client = AsyncClient( base_url=self._base_url,
                                    timeout=self._settings.REQUEST_TIMEOUT,
                                    follow_redirects=True,
                                    headers=self._headers )
        log_message( LG.API, "کلاینت API دیجی‌کالا با موفقیت راه‌اندازی شد", LogLevel.DEBUG )
        return self

    async def __aexit__( self, exc_type, exc_val, exc_tb ) -> bool:
        """‫بستن کلاینت و آزادسازی منابع شبکه"""
        if self._client:
            await self._client.aclose()
            log_message( LG.API, "کلاینت API دیجی‌کالا بسته شد", LogLevel.DEBUG )
        return False

    @retry(
        stop=stop_after_attempt( get_settings().MAX_RETRIES ),
        wait=wait_exponential( multiplier=1, min=2, max=10 ),
        retry=retry_if_exception_type( HTTPStatusError ),
        reraise=True,
    )
    async def _safe_request( self, url: str, params: dict[ str, str | int ] | None = None ) -> dict:
        """‫اجرای درخواست HTTP با مدیریت خطا، Retry و کنترل نرخ درخواست

        Args:
            url: مسیر نسبی Endpoint
            params: پارامترهای کوئری (اختیاری)

        Returns:
            دیکشنری خام پاسخ JSON

        Raises:
            RuntimeError: اگر کلاینت قبل از ورود به Context Manager فراخوانی شود
            HTTPStatusError: در صورت خطای HTTP پس از اتمام تلاش‌های مجدد
        """
        async with self._semaphore:
            if self._client is None:
                raise RuntimeError( "کلاینت HTTP راه‌اندازی نشده است. از `async with` استفاده کنید." )

            response = await self._client.get( url, params=params )
            response.raise_for_status()

            # ‫رعایت Rate Limiting بین درخواست‌ها
            await asyncio.sleep( self._settings.REQUEST_DELAY_SECONDS )
            return response.json()

    async def fetch_product_list( self, page: int = 1 ) -> DigikaiaProductListResponse:
        """‫دریافت لیست محصولات از یک صفحه مشخص

        Args:
            page: شماره صفحه (پیش‌فرض 1)

        Returns:
            مدل اعتبارسنجی‌شده لیست محصولات

        Raises:
            ValidationError: اگر ساختار پاسخ API با مدل Pydantic همخوانی نداشته باشد
        """
        log_message( LG.API, f"درخواست لیست محصولات | صفحه: {page}", LogLevel.DEBUG )
        raw_data = await self._safe_request( "/v1/categories/mobile-phone/search/", params={ "page": page } )

        try:
            return DigikaiaProductListResponse.model_validate( raw_data )
        except ValidationError as exc:
            log_message( LG.API, f"خطای اعتبارسنجی لیست محصولات صفحه {page}: {exc}", LogLevel.ERROR )
            raise

    async def fetch_product_detail( self, product_id: int ) -> DigikaiaProductDetailResponse:
        """‫دریافت جزئیات کامل یک محصول بر اساس شناسه

        Args:
            product_id: شناسه عددی محصول

        Returns:
            مدل اعتبارسنجی‌شده جزئیات محصول

        Raises:
            ValidationError: اگر ساختار پاسخ API با مدل Pydantic همخوانی نداشته باشد
        """
        log_message( LG.API, f"درخواست جزئیات محصول | ID: {product_id}", LogLevel.DEBUG )
        raw_data = await self._safe_request( f"/v2/product/{product_id}/" )

        try:
            return DigikaiaProductDetailResponse.model_validate( raw_data )
        except ValidationError as exc:
            log_message( LG.API, f"خطای اعتبارسنجی محصول {product_id}: {exc}", LogLevel.ERROR )
            raise

    async def stream_product_ids( self, start_page: int = 1, max_pages: int | None = None ) -> AsyncIterator[ int ]:
        """‫ژنراتور غیرهمزمان برای پیمایش خودکار صفحات و استخراج ID محصولات

        Args:
            start_page: صفحه شروع
            max_pages: حداکثر تعداد صفحات برای پیمایش (None = ادامه تا آخرین صفحه)

        Yields:
            شناسه عددی هر محصول به صورت ترتیبی
        """
        current_page = start_page
        while max_pages is None or current_page <= max_pages + start_page - 1:
            try:
                list_response = await self.fetch_product_list( page=current_page )

                for item in list_response.data.products:
                    yield item.id

                # ‫بررسی پایان صفحات
                if current_page >= list_response.data.pager.total_pages:
                    log_message( LG.API, "پیمایش به پایان رسید (تمام صفحات پردازش شد)", LogLevel.INFO )
                    break

                current_page += 1
            except ( HTTPStatusError, ValidationError ) as exc:
                log_message( LG.API, f"توقف پیمایش در صفحه {current_page} به دلیل خطا: {exc}", LogLevel.ERROR )
                break
