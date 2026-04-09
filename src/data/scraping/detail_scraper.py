# ==================== Imports  ====================
import asyncio
import json
import random
import re
from pathlib import Path
import httpx
# ==================== Imports داخلی پروژه ====================
from src.config.logging_config import LG, LogLevel, log_message
from src.config.settings import get_settings
from src.data.models.product import Product, ProductOffer, ProductSpecs

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

# ‫الگوهای regex برای استخراج داده از HTML
_RE_PRODUCT_BLOCK = re.compile(
    r'\{"_id":"[^"]+","code":"TLP-(\d+)"(.+?)"score_avg":([\d.]+)',
    re.DOTALL,
)
_RE_TITLE = re.compile( r'"title":"([^"]+)"' )
_RE_MODEL = re.compile( r'"model":"([^"]+)"' )
_RE_BRAND_FA = re.compile( r'"brand":\{"name":"([^"]+)"' )
_RE_BRAND_EN = re.compile( r'"brand":\{[^}]+"enName":"([^"]+)"' )
_RE_CATEGORY = re.compile( r'"category":\{"code":"[^"]+","name":"([^"]+)"' )
_RE_IS_AVAILABLE = re.compile( r'"is_available":(true|false)' )
_RE_CANONICAL = re.compile( r'"canonical":"(https://www\.technolife\.com/product-\d+/[^"]+)"' )
_RE_IMAGE = re.compile( r'/image/small_product-TLP-\d+[^"]*\.(?:png|jpg|webp)' )
_RE_SCORE_COUNT = re.compile( r'"score_count":(\d+)' )

# ‫الگو برای icons (مشخصات کلیدی)
_RE_ICONS = re.compile( r'"icons":\[(\{.+?\})\]', re.DOTALL )          #TODO ‫چرا از اسم ICONS استفاده شده؟
_RE_ICON_ITEM = re.compile( r'\{"font":"([^"]+)","value":"([^"]+)","title":"([^"]+)"\}' )

_RE_COLOR_IN_OFFER = re.compile( r'"color":\{"code":"([^"]+)","value":"([^"]+)"' )


# ==================== توابع کمکی داخلی====================
def _parse_icons( html: str ) -> ProductSpecs:
    """‫استخراج مشخصات فنی از icons"""

    # ‫mapping از font icon به فیلد
    icon_map = {
        "icon-processors": "cpu",
        "icon-hard-disk-drive": "storage",
        "icon-ram": "ram",
        "icon-smartphone-1": "screen_size",
        "icon-photo-camera": "camera_rear",
        "icon-battery-1": "battery",
    }

    specs_data: dict[ str, str ] = {}
    icons_match = _RE_ICONS.search( html )
    if not icons_match:
        return ProductSpecs()

    for item in _RE_ICON_ITEM.finditer( icons_match.group( 0 ) ):
        font, value, _ = item.group( 1 ), item.group( 2 ), item.group( 3 )
        field = icon_map.get( font )
        if field:
            specs_data[ field ] = value.strip()

    return ProductSpecs( **specs_data )


def _parse_offers( html: str ) -> tuple[ list[ ProductOffer ], ProductOffer | None ]:
    """‫استخراج همه offer ها و offer اصلی تکنولایف

    ‫خروجی:
        (همه offer ها, offer تکنولایف یا اولین offer)
    """
    offers: list[ ProductOffer ] = []
    techno_offer: ProductOffer | None = None

    # ‫پیدا کردن همه بلاک‌های offer
    offer_blocks = list( re.finditer( r'"seller_code":"(TLS-[^"]+)".*?"is_techno":(true|false)', html, re.DOTALL ) )

    for block_match in offer_blocks:
        block_start = html.rfind( '{"name":"بیمه', 0, block_match.start() )
        if block_start == -1:
            block_start = html.rfind( '{"_id":', 0, block_match.start() )
        if block_start == -1:
            continue

        block = html[ block_start:block_match.end() + 100 ]

        # ‫استخراج رنگ
        color_m = _RE_COLOR_IN_OFFER.search( html[ max( 0, block_start - 200 ):block_start + 50 ] )
        color_code = color_m.group( 1 ) if color_m else None
        color_name = color_m.group( 2 ) if color_m else None

        # ‫استخراج قیمت و موجودی
        price_m = re.search( r'"price":(\d+)', block )
        disc_price_m = re.search( r'"discounted_price":(\d+)', block )
        in_stock_m = re.search( r'"in_stock":(\d+)', block )
        stock_text_m = re.search( r'"stock_text":"([^"]+)"', block )
        delivery_m = re.search( r'"delivery_text":"([^"]+)"', block )
        is_techno = block_match.group( 2 ) == "true"

        if not price_m:
            continue

        price = int( price_m.group( 1 ) )
        disc_price = int( disc_price_m.group( 1 ) ) if disc_price_m else price

        # ‫محاسبه درصد تخفیف
        discount_percent: int | None = None
        if disc_price < price and price > 0:
            discount_percent = round( ( price - disc_price ) / price * 100 )

        offer = ProductOffer(
            color_code=color_code,
            color_name=color_name,
            price=price,
            discounted_price=disc_price,
            discount_percent=discount_percent,
            in_stock=int( in_stock_m.group( 1 ) ) if in_stock_m else 0,
            stock_text=stock_text_m.group( 1 ) if stock_text_m else None,
            delivery_text=delivery_m.group( 1 ) if delivery_m else None,
            is_techno=is_techno,
        )

        offers.append( offer )
        if is_techno and techno_offer is None:
            techno_offer = offer

    # ‫اگه offer تکنولایف نبود، اولین offer رو برمیگردانیم
    if techno_offer is None and offers:
        techno_offer = offers[ 0 ]

    return offers, techno_offer


# ==================== توابع  اصلی====================
def parse_product( html: str, product_id: int ) -> Product | None:
    """‫استخراج اطلاعات محصول از HTML صفحه

    ‫پارامترها:
        html: محتوای HTML صفحه محصول
        product_id: شناسه عددی محصول

    ‫خروجی:
        Product یا None در صورت شکست parse
    """
    # ‫استخراج فیلدهای پایه
    title_m = _RE_TITLE.search( html )
    if not title_m:
        log_message( LG.SCRAPING, f"محصول {product_id}: title یافت نشد", LogLevel.WARNING )
        return None

    code_m = re.search( r'"code":"(TLP-\d+)"', html )
    model_m = _RE_MODEL.search( html )
    brand_fa_m = _RE_BRAND_FA.search( html )
    brand_en_m = _RE_BRAND_EN.search( html )
    category_m = _RE_CATEGORY.search( html )
    available_m = _RE_IS_AVAILABLE.search( html )
    canonical_m = _RE_CANONICAL.search( html )
    image_m = _RE_IMAGE.search( html )
    score_count_m = _RE_SCORE_COUNT.search( html )
    score_avg_m = _RE_PRODUCT_BLOCK.search( html )

    # ‫استخراج مشخصات فنی و offer ها
    specs = _parse_icons( html )
    offers, main_offer = _parse_offers( html )

    if main_offer is None:
        log_message( LG.SCRAPING, f"محصول {product_id}: offer یافت نشد", LogLevel.WARNING )
        return None

    # ‫ساخت URL تصویر کامل
    image_url: str | None = None
    if image_m:
        image_url = f"{BASE_URL}{image_m.group(0)}"

    return Product(
        product_id=product_id,
        code=code_m.group( 1 ) if code_m else f"TLP-{product_id}",
        name=title_m.group( 1 ),
        model=model_m.group( 1 ) if model_m else None,
        brand_fa=brand_fa_m.group( 1 ) if brand_fa_m else None,
        brand_en=brand_en_m.group( 1 ) if brand_en_m else None,
        category=category_m.group( 1 ) if category_m else None,
        price=main_offer.price,
        discounted_price=main_offer.discounted_price,
        is_available=available_m.group( 1 ) == "true" if available_m else False,
        stock_text=main_offer.stock_text,
        delivery_text=main_offer.delivery_text,
        offers=offers,
        specs=specs,
        score_avg=float( score_avg_m.group( 3 ) ) if score_avg_m else None,
        score_count=int( score_count_m.group( 1 ) ) if score_count_m else None,
        url=canonical_m.group( 1 ) if canonical_m else f"{BASE_URL}/product-{product_id}/",
        image_url=image_url,
    )


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
