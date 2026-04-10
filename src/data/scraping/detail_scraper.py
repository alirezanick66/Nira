import asyncio
import json
import random
from pathlib import Path

import httpx

from src.config.logging_config import LG, LogLevel, log_message
from src.config.settings import get_settings
from src.data.models.product import Product
from src.data.scraping.parsers import parse_product

settings = get_settings()
BASE_URL = settings.SCRAPING_BASE_URL
HEADERS = {
    "User-Agent": ( "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36" ),
    "Accept-Language":
    "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def scrape_product(
    client: httpx.AsyncClient,
    product_id: int,
) -> Product | None:
    """دریافت و parse صفحه یک محصول با مدیریت Retry"""
    url = f"{BASE_URL}/product-{product_id}/"

    for attempt in range( 1, settings.SCRAPING_MAX_RETRIES + 1 ):
        try:
            response = await client.get( url, timeout=30 )
            response.raise_for_status()
            product = parse_product( response.text, product_id )

            if product:
                log_message( LG.SCRAPING, f"محصول {product_id}: استخراج موفق — {product.name[:40]}", LogLevel.INFO )
            return product

        except httpx.HTTPStatusError as e:
            log_message( LG.SCRAPING, f"محصول {product_id} — خطای HTTP {e.response.status_code} — تلاش {attempt}", LogLevel.WARNING )
        except httpx.RequestError as e:
            log_message( LG.SCRAPING, f"محصول {product_id} — خطای اتصال — تلاش {attempt}: {e}", LogLevel.WARNING )

        if attempt < settings.SCRAPING_MAX_RETRIES:
            await asyncio.sleep( random.uniform( 3, 6 ) )

    log_message( LG.SCRAPING, f"محصول {product_id} — همه تلاش‌ها ناموفق", LogLevel.ERROR )
    return None


async def scrape_products(
    product_ids: list[ int ],
    output_path: Path,
) -> list[ Product ]:
    """استخراج جزئیات همه محصولات به‌صورت همزمان با محدودیت Semaphore"""
    products: list[ Product ] = []
    failed: list[ int ] = []
    SCRAPING_CONCURRENCY: int = 5
    # Semaphore تعداد درخواست‌های همزمان را به SCRAPING_CONCURRENCY محدود می‌کند
    semaphore = asyncio.Semaphore( SCRAPING_CONCURRENCY )

    async with httpx.AsyncClient( headers=HEADERS, follow_redirects=True ) as client:

        async def _scrape_with_limit( pid: int ) -> Product | None:
            async with semaphore:
                # ‫تأخیر کوتاه و تصادفی برای جلوگیری از تشخیص Burst توسط WAF سایت
                await asyncio.sleep( random.uniform( 0.2, 0.5 ) )
                result = await scrape_product( client, pid )
                if isinstance( result, Product ):
                    products.append( result )
                    if len( products ) % 50 == 0:
                        await _save_products( products, output_path )
                return result

        # ایجاد و اجرای همزمان تسک‌ها
        tasks = [ _scrape_with_limit( pid ) for pid in product_ids ]
        results = await asyncio.gather( *tasks, return_exceptions=True )

        # پردازش نتایج
        for pid, result in zip( product_ids, results ):
            if isinstance( result, Exception ) or result is None:
                failed.append( pid )
                log_message( LG.SCRAPING, f"محصول {pid} — خطای غیرمنتظره: {result}", LogLevel.ERROR )
            elif isinstance( result, Product ):
                products.append( result )
            else:
                failed.append( pid )

    # ذخیره نهایی
    await _save_products( products, output_path )

    log_message(
        LG.SCRAPING,
        f"اتمام — موفق: {len(products)} | ناموفق: {len(failed)}",
        LogLevel.INFO,
        failed_ids=failed[ :10 ] if failed else [],
    )
    return products


async def _save_products( products: list[ Product ], output_path: Path ) -> None:
    """ذخیره محصولات در فایل JSON به‌صورت غیرمسدودکننده"""

    def _blocking_write() -> None:
        output_path.parent.mkdir( parents=True, exist_ok=True )
        data = [ p.model_dump( mode="json" ) for p in products ]
        output_path.write_text(
            json.dumps( {
                "products": data,
                "total": len( data )
            }, ensure_ascii=False, indent=2 ),
            encoding="utf-8",
        )

    await asyncio.to_thread( _blocking_write )
    log_message( LG.SCRAPING, f"ذخیره شد: {output_path} — {len(products)} محصول", LogLevel.INFO )
