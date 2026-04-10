# ==================== Imports  ====================
import re
# ==================== Imports داخلی پروژه ====================
from src.data.models.product import Product, ProductOffer, ProductSpecs
from src.config.logging_config import LG, LogLevel, log_message
from src.config.settings import get_settings

settings = get_settings()
BASE_URL = settings.SCRAPING_BASE_URL

# ‫الگوهای پایه برای استخراج داده از HTML
_RE_PRODUCT_BLOCK = re.compile( r'\{"_id":"[^"]+","code":"TLP-(\d+)"(.+?)"score_avg":([\d.]+)', re.DOTALL )
_RE_TITLE = re.compile( r'"title":"([^"]+)"' )
_RE_MODEL = re.compile( r'"model":"([^"]+)"' )
_RE_BRAND_FA = re.compile( r'"brand":\{"name":"([^"]+)"' )
_RE_BRAND_EN = re.compile( r'"brand":\{[^}]+"enName":"([^"]+)"' )
_RE_CATEGORY = re.compile( r'"category":\{"code":"[^"]+","name":"([^"]+)"' )
_RE_IS_AVAILABLE = re.compile( r'"is_available":(true|false)' )
_RE_CANONICAL = re.compile( r'"canonical":"(https://www\.technolife\.com/product-\d+/[^"]+)"' )
_RE_IMAGE = re.compile( r'/image/small_product-TLP-\d+[^"]*\.(?:png|jpg|webp)' )
_RE_SCORE_COUNT = re.compile( r'"score_count":(\d+)' )
_RE_NAME = re.compile( r'<strong[^>]*id=["\']pdp_name["\'][^>]*>(.*?)</strong>', re.DOTALL )
# _RE_COLOR_IN_OFFER = re.compile( r'"color":\{"code":"([^"]+)","value":"([^"]+)"' ) #رنگ محصول

# ‫الگو استخراج ردیف‌های مشخصات فنی از <li>
_RE_SPEC_ROW = re.compile( r'<li[^>]*>.*?<p[^>]*>(.*?)</p>.*?<p[^>]*>(.*?)</p>.*?</li>', re.DOTALL )

# ‫نگاشت کلیدهای HTML به فیلدهای مدل
_SPEC_KEY_MAP: dict[ str, str ] = {
    "نوع پردازنده": "cpu",
    "تعداد هسته پردازشگر": "cpu_cores",
    "پردازنده گرافیکی": "gpu",
    "کیفیت دوربین": "camera_quality",
    "نوع سیستم عامل": "os",
    "تاریخ معرفی": "release_date",
    "ابعاد/ وزن": "dimensions_weight",
    "حافظه داخلی": "internal_storage",
    "حافظه ram": "ram",
    "امکان افزایش حافظه": "expandable_storage",
    "نوع صفحه نمایش": "display_type",
    "سایز صفحه نمایش": "display_size",
    "تعداد رنگ": "display_colors_resolution",
    "درصد نسبت صفحه نمایش به بدنه": "screen_to_body_ratio",
    "نسبت صفحه نمایش": "aspect_ratio",
    "تراکم پیکسل": "pixel_density",
    "مولتی تاچ": "multi_touch",
    "دوربین پشت": "rear_camera",
    "مشخصات سخت‌ افزاری دوربین": "camera_hardware",
    "فیلمبرداری دوربین پشت": "rear_video",
    "فلاش": "flash",
    "زوم دیجیتال": "digital_zoom",
    "دوربین جلو": "front_camera",
    "سایر ویژگی‌ های مهم دوربین": "camera_features",
    "شبکه اینترنت": "network_internet",
    "شبکه‌ های مخابراتی قابل پشتیبانی": "cellular_networks",
    "حداکثر سرعت دانلود": "umts_speed",
    "پورت usb": "usb_port",
    "امکان شارژ از طریق usb": "usb_charging",
    "بلوتوث": "bluetooth",
    "جک 3.5 میلی متری صدا": "audio_jack",
    "شبکه wi-fi": "wifi",
    "امکان wi-fi hotspot": "wifi_hotspot",
    "خروجی hdmi": "hdmi_output",
    "موقعیت‌ نما gps": "gps",
    "مرورگر وب": "web_browser",
    "پشتیبانی از java": "java_support",
    "پخش موسیقی": "music_formats",
    "ضبط صدا": "audio_recording_formats",
    "پخش ویدئو": "video_formats",
    "ضبط ویدئو": "video_recording_formats",
    "نمایش عکس": "photo_formats",
    "فرمت عکس‌ های دوربین": "camera_photo_format",
    "سنسورها": "sensors",
    "مقاومت در برابر آب و گرد و غبار": "water_dust_resistance",
    "رادیو": "radio",
    "سایر مشخصات مهم": "other_features",
    "باتری": "battery",
    "ظرفیت باتری": "battery_capacity",
    "نوع باتری": "battery_type",
    "شناسه کالا": "product_code",
}


# ==================== توابع کمکی داخلی====================
def _parse_specs( html: str ) -> ProductSpecs:
    """‫استخراج مشخصات فنی کامل از بخش لیست جزییات"""
    specs_data: dict[ str, str ] = {}

    # جلوگیری از تداخل زیررشته‌ها (مثلاً تطابق "باتری" به جای "ظرفیت باتری")
    sorted_key_map = sorted( _SPEC_KEY_MAP.items(), key=lambda item: len( item[ 0 ] ), reverse=True )

    for match in _RE_SPEC_ROW.finditer( html ):
        raw_key = match.group( 1 ).strip().rstrip( ':' ).strip()
        value = match.group( 2 ).strip()

        # ‫نرمال‌سازی کلید برای تطبیق امن‌تر با نگاشت
        norm_key = raw_key.replace( '\u200c', ' ' ).lower()

        for map_key, field_name in sorted_key_map:
            if map_key.replace( '\u200c', ' ' ).lower() in norm_key:
                specs_data[ field_name ] = value
                break

    return ProductSpecs( **specs_data )


def parse_offers( html: str ) -> tuple[ list[ ProductOffer ], ProductOffer | None ]:
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
        # color_m = _RE_COLOR_IN_OFFER.search( html[ max( 0, block_start - 200 ):block_start + 50 ] )
        # color_code = color_m.group( 1 ) if color_m else None
        # color_name = color_m.group( 2 ) if color_m else None

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
          # color_code=color_code,
          # color_name=color_name,
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


def parse_product( html: str, product_id: int ) -> Product | None:
    """‫استخراج اطلاعات محصول از HTML صفحه

    ‫پارامترها:
        html: محتوای HTML صفحه محصول
        product_id: شناسه عددی محصول

    ‫خروجی:
        Product یا None در صورت شکست parse
    """
    # ‫استخراج فیلدهای پایه
    name_m = _RE_NAME.search( html )
    if not name_m:
        log_message( LG.SCRAPING, f"محصول {product_id}: نام محصول (pdp_name) یافت نشد", LogLevel.WARNING )
        return None

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
    specs = _parse_specs( html )
    offers, main_offer = parse_offers( html )
    is_available = available_m.group( 1 ) == "true" if available_m else False

    # ‫محصول ناموجود — offer نداره ولی باید ذخیره بشه
    if main_offer is None and not is_available:
        log_message( LG.SCRAPING, f"محصول {product_id}: ناموجود — بدون offer", LogLevel.INFO )
        main_offer = ProductOffer( price=0, discounted_price=0 )

    elif main_offer is None:
        log_message( LG.SCRAPING, f"محصول {product_id}: offer یافت نشد", LogLevel.WARNING )
        return None

    # ‫ساخت URL تصویر کامل
    image_url: str | None = None
    if image_m:
        image_url = f"{BASE_URL}{image_m.group(0)}"

    return Product(
        product_id=product_id,
        name=name_m.group( 1 ),
        model=model_m.group( 1 ) if model_m else None,
        brand_fa=brand_fa_m.group( 1 ) if brand_fa_m else None,
        brand_en=brand_en_m.group( 1 ) if brand_en_m else None,
        category=category_m.group( 1 ) if category_m else None,
        price=main_offer.price,
        discounted_price=main_offer.discounted_price,
        is_available=is_available,
        stock_text=main_offer.stock_text,
        delivery_text=main_offer.delivery_text,
        offers=offers,
        specs=specs,
        score_avg=float( score_avg_m.group( 3 ) ) if score_avg_m else None,
        score_count=int( score_count_m.group( 1 ) ) if score_count_m else None,
        url=canonical_m.group( 1 ) if canonical_m else f"{BASE_URL}/product-{product_id}/",
        image_url=image_url,
    )
