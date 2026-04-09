# ==================== Imports ====================
import asyncio
import json
import re
import random
from pathlib import Path
import httpx

# ==================== Imports داخلی پروژه ====================
from nira.config.logging_config import LG, LogLevel, log_message
from nira.config.settings import get_settings

# ==================== متغیرهای داخلی ====================
settings = get_settings()
base_url = settings.SCRAPING_BASE_URL
# ‫آدرس صفحه لیست محصولات موبایل
LIST_URL = ( f"{base_url}/product/list/69_800_801"
             f"/%D8%AA%D9%85%D8%A7%D9%85%DB%8C-%DA%AF%D9%88%D8%B4%DB%8C%E2%80%8C%D9%87%D8%A7" )

# ‫آدرس جدیدترین محصولات برای آپدیت‌های بعدی
NEW_PRODUCTS_URL = LIST_URL + "?ordering=date-desc"

# ‫تعداد کل صفحات
TOTAL_PAGES = 83

# ‫الگوی استخراج ID محصول از href
PRODUCT_ID_PATTERN = re.compile( r'href="/product-(\d+)/' )

# ‫هدرهای HTTP برای شبیه‌سازی browser واقعی
HEADERS = {
    "User-Agent": ( "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36" ),
    "Accept-Language":
    "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept":
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ==================== توابع کمکی داخلی====================
def _build_page_url( page: int ) -> str:
    """‫ساخت URL صفحه مشخص از لیست محصولات"""
    if page == 1:
        return f"{LIST_URL}?page=1"
    return f"{LIST_URL}?page={page}"


def _extract_ids_from_html( html: str ) -> set[ int ]:
    """‫استخراج ID محصولات از محتوای HTML"""
    matches = PRODUCT_ID_PATTERN.findall( html )
    return { int( product_id ) for product_id in matches }


async def _fetch_page( client: httpx.AsyncClient, url: str, page: int ) -> set[ int ]:
    """‫دریافت یک صفحه و استخراج IDهای محصولات

    ‫پارامترها:
        client: کلاینت HTTP
        url: آدرس صفحه
        page: شماره صفحه (برای لاگ)
    """
    for attempt in range( 1, settings.SCRAPING_MAX_RETRIES + 1 ):
        try:
            response = await client.get( url, timeout=30 )
            response.raise_for_status()

            ids = _extract_ids_from_html( response.text )
            log_message( LG.SCRAPING, f"صفحه {page}: {len(ids)} محصول استخراج شد", LogLevel.INFO )
            return ids

        except httpx.HTTPStatusError as e:
            log_message( LG.SCRAPING, f"صفحه {page} — خطای HTTP {e.response.status_code} — تلاش {attempt}", LogLevel.WARNING )
        except httpx.RequestError as e:
            log_message( LG.SCRAPING, f"صفحه {page} — خطای اتصال — تلاش {attempt}: {e}", LogLevel.WARNING )

        if attempt < settings.SCRAPING_MAX_RETRIES:
            await asyncio.sleep( random.uniform( 3, 6 ) )

    log_message( LG.SCRAPING, f"صفحه {page} — همه تلاش‌ها ناموفق بود", LogLevel.ERROR )
    return set()


# ==================== توابع  اصلی====================
async def collect_all_ids( total_pages: int = TOTAL_PAGES ) -> list[ int ]:
    """‫جمع‌آوری ID تمام محصولات از همه صفحات لیست

    ‫پارامترها:
        total_pages: تعداد کل صفحات (پیش‌فرض ۸۳)

    ‫خروجی:
        لیست مرتب‌شده ID محصولات یکتا
    """
    all_ids: set[ int ] = set()

    async with httpx.AsyncClient( headers=HEADERS, follow_redirects=True ) as client:
        for page in range( 1, total_pages + 1 ):
            url = _build_page_url( page )
            ids = await _fetch_page( client, url, page )
            all_ids.update( ids )

            # ‫delay تصادفی برای جلوگیری از بلاک شدن
            delay = random.uniform(
                settings.SCRAPING_DELAY_SECONDS,
                settings.SCRAPING_DELAY_SECONDS * 2,
            )
            await asyncio.sleep( delay )

    result = sorted( all_ids )
    log_message( LG.SCRAPING, f"جمع‌آوری کامل شد — {len(result)} محصول یکتا", LogLevel.INFO )
    return result


async def collect_new_ids( existing_ids: set[ int ], pages: int = 3 ) -> list[ int ]:
    """‫جمع‌آوری IDهای جدید (محصولاتی که قبلاً نداشتیم و نیاز به آپدیت هستش)

    ‫پارامترها:
        existing_ids: مجموعه IDهایی که از قبل داریم
        pages: تعداد صفحات اول برای بررسی (پیش‌فرض ۳)

    ‫خروجی:
        لیست IDهای جدید
    """
    new_ids: set[ int ] = set()

    async with httpx.AsyncClient( headers=HEADERS, follow_redirects=True ) as client:
        for page in range( 1, pages + 1 ):
            url = f"{NEW_PRODUCTS_URL}&page={page}"
            ids = await _fetch_page( client, url, page )

            # ‫فقط IDهایی که قبلاً نداشتیم
            fresh = ids - existing_ids
            new_ids.update( fresh )

            # ‫اگه صفحه‌ای هیچ ID جدیدی نداشت، ادامه لازم نیست
            if not fresh:
                log_message( LG.SCRAPING, f"صفحه {page} — محصول جدیدی یافت نشد، توقف", LogLevel.INFO )
                break

            await asyncio.sleep( random.uniform(
                settings.SCRAPING_DELAY_SECONDS,
                settings.SCRAPING_DELAY_SECONDS * 2,
            ) )

    result = sorted( new_ids )
    log_message( LG.SCRAPING, f"آپدیت کامل شد — {len(result)} محصول جدید", LogLevel.INFO )
    return result


def save_ids( ids: list[ int ], output_path: Path ) -> None:
    """‫ذخیره لیست IDها در فایل JSON

    ‫پارامترها:
        ids: لیست IDهای محصولات
        output_path: مسیر فایل خروجی
    """
    output_path.parent.mkdir( parents=True, exist_ok=True )
    output_path.write_text(
        json.dumps( {
            "product_ids": ids,
            "total": len( ids )
        }, ensure_ascii=False, indent=2 ),
        encoding="utf-8",
    )
    log_message( LG.SCRAPING, f"ذخیره شد: {output_path} — {len(ids)} محصول", LogLevel.INFO )


def load_ids( input_path: Path ) -> list[ int ]:
    """‫بارگذاری لیست IDها از فایل JSON

    ‫پارامترها:
        input_path: مسیر فایل JSON

    ‫خروجی:
        لیست IDهای محصولات
    """
    data = json.loads( input_path.read_text( encoding="utf-8" ) )
    return data[ "product_ids" ]
