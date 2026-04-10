# ==================== Imports  ====================
import asyncio
import json
import random

from pathlib import Path
import httpx
# ==================== Imports داخلی پروژه ====================
from src.config.logging_config import LG, LogLevel, log_message
from src.config.settings import get_settings
from src.data.models.product import Product
from src.data.scraping.parsers import parse_product
# ==================== متغیرهای داخلی ====================
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


# ==================== توابع  اصلی====================
async def scrape_product(
    client: httpx.AsyncClient,
    product_id: int,
) -> Product | None:
    """‫دریافت و parse صفحه یک محصول

    ‫پارامترها:
        client: کلاینت HTTP
        product_id: شناسه عددی محصول
    """
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
    """‫استخراج جزئیات همه محصولات و ذخیره در فایل JSON

    ‫پارامترها:
        product_ids: لیست شناسه‌های محصولات
        output_path: مسیر فایل خروجی JSON
    """
    products: list[ Product ] = []
    failed: list[ int ] = []

    async with httpx.AsyncClient( headers=HEADERS, follow_redirects=True ) as client:
        for i, product_id in enumerate( product_ids, 1 ):
            log_message( LG.SCRAPING, f"پردازش {i}/{len(product_ids)} — محصول {product_id}", LogLevel.INFO )

            product = await scrape_product( client, product_id )

            if product:
                products.append( product )
            else:
                failed.append( product_id )

            # ‫ذخیره هر 50 محصول (برای جلوگیری از از دست رفتن داده)
            if len( products ) % 50 == 0 and products:
                await _save_products( products, output_path )

            # ‫delay بین request ها
            if i < len( product_ids ):
                await asyncio.sleep( random.uniform( settings.SCRAPING_DELAY_SECONDS, settings.SCRAPING_DELAY_SECONDS * 2 ) )

    # ‫ذخیره نهایی
    await _save_products( products, output_path )

    log_message(
        LG.SCRAPING,
        f"اتمام — موفق: {len(products)} | ناموفق: {len(failed)}",
        LogLevel.INFO,
        failed_ids=failed[ :10 ] if failed else [],
    )

    return products


async def _save_products( products: list[ Product ], output_path: Path ) -> None:
    """‫ذخیره محصولات در فایل JSON"""

    def _blocking_write():
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
