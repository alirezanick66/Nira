from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProductOffer( BaseModel ):
    """‫اطلاعات قیمت و موجودی یک رنگ/فروشنده"""

    # color_name: str | None = None
    # color_code: str | None = None
    price: int = Field( ge=0 )
    discounted_price: int = Field( ge=0 )
    discount_percent: int | None = None
    in_stock: int = Field( default=0, ge=0 )
    stock_text: str | None = None
    delivery_text: str | None = None
    is_techno: bool = False


class ProductSpecs( BaseModel ):
    """‫مشخصات فنی محصول — استخراج از icons"""

    cpu: str | None = None
    ram: str | None = None
    storage: str | None = None
    screen_size: str | None = None
    camera_rear: str | None = None
    battery: str | None = None


class Product( BaseModel ):
    """‫مدل اصلی محصول — خروجی detail_scraper"""

    # ‫اطلاعات پایه
    product_id: int = Field( description="‫شناسه عددی محصول از URL" )
    name: str
    model: str | None = None
    brand_fa: str | None = None
    brand_en: str | None = None
    category: str | None = None

    # ‫قیمت و موجودی — offer اصلی تکنولایف
    price: int = Field( ge=0 )
    discounted_price: int = Field( ge=0 )
    is_available: bool
    stock_text: str | None = None
    delivery_text: str | None = None

    # ‫همه offer ها (رنگ‌های مختلف)
    offers: list[ ProductOffer ] = Field( default_factory=list )

    # ‫مشخصات فنی
    specs: ProductSpecs = Field( default_factory=ProductSpecs )

    # ‫امتیاز
    score_avg: float | None = Field( default=None, ge=0, le=5 )
    score_count: int | None = Field( default=None, ge=0 )

    # ‫لینک‌ها
    url: str
    image_url: str | None = None

    # ‫زمان scraping
    scraped_at: datetime = Field( default_factory=datetime.utcnow )

    @field_validator( "product_id" )
    @classmethod
    def validate_product_id( cls, value: int ) -> int:
        """‫اعتبارسنجی ID محصول"""
        if value <= 0:
            raise ValueError( "‫product_id باید مثبت باشد" )
        return value
