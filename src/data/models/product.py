"""مدل محصول نرمال‌شده برای استفاده داخلی
‫این مدل ساختار تمیز و استانداردی را ارائه می‌دهد که:
-‫ مستقل از ساختار API دیجی‌کالا
- ‫آماده ذخیره در PostgreSQL
-‫ آماده تبدیل به QdrantPayload
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict


#────────────────────────────────────────── Enums ──────────────────────────────────────────
class ProductCategory( str, Enum ):
    """دسته‌بندی‌های مجاز محصولات"""
    MOBILE = "موبایل"
    HEADPHONE = "هدفون"
    EARPHONE = "هندزفری"


class ProductStatus( str, Enum ):
    """وضعیت موجودی محصول در فروشگاه"""
    MARKETABLE = "marketable"
    OUT_OF_STOCK = "out_of_stock"


class PriceRange( str, Enum ):
    """بازه‌های قیمتی استاندارد (تومان)"""

    BUDGET = "budget"          # تا 10 میلیون
    MID = "mid"          # 10-30 میلیون
    PREMIUM = "premium"          # 30-60 میلیون
    FLAGSHIP = "flagship"          # بالای 60 میلیون


class QualityLevel( str, Enum ):
    """‫سطح کیفیت (برای استنتاج از specs/reviews)"""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
    UNKNOWN = "unknown"


#────────────────────────────────────────── Nested Models ──────────────────────────────────────────


class ReviewSectionItem( BaseModel ):
    """‫آیتم محتوایی در بخش‌های نقد تخصصی"""
    model_config = ConfigDict( extra="ignore" )
    text: str | None = Field( default=None, description="متن بخش نقد" )


class ExpertReview( BaseModel ):
    """ساختار نقد و بررسی تخصصی محصول"""

    description: str = Field( description="توضیحات اصلی نقد" )
    sections: list[ ReviewSectionItem ] = Field( default_factory=list, description="‫بخش‌های نقد (JSON)" )

    def get_summary( self, max_length: int = 500 ) -> str:
        """دریافت خلاصه‌ی توضیحات اصلی با حداکثر طول مشخص
        
        Args:
            max_length: حداکثر تعداد کاراکتر خروجی
        
        Returns:
            رشته خلاصه‌شده
        """
        if len( self.description ) <= max_length:
            return self.description
        return self.description[ :max_length ] + "..."


class UserFeedback( BaseModel ):
    """خلاصه بازخوردها و نظرات کاربران"""

    overview: str = Field( description="خلاصه کلی نظرات کاربران" )
    advantages: list[ str ] = Field( default_factory=list, description="مزایای ذکرشده" )
    disadvantages: list[ str ] = Field( default_factory=list, description="معایب ذکرشده" )

    def get_summary( self, max_length: int = 300 ) -> str:
        """دریافت خلاصه‌ی مرور کلی کاربران
        
        Args:
            max_length: حداکثر تعداد کاراکتر خروجی
        
        Returns:
            رشته خلاصه‌شده
        """
        if len( self.overview ) <= max_length:
            return self.overview
        return self.overview[ :max_length ] + "..."


class ProductSpecification( BaseModel ):
    """مشخصات فنی کلیدی و نرمال‌شده محصول"""

    # مشخصات خام
    raw_specifications: list[ dict ] = Field( default_factory=list, description="داده‌های خام specifications از API" )

    # مشخصات نرمال‌شده (فیلدهای کلیدی)
    ram_gb: float | None = Field( default=None, ge=0, description="‫رم (گیگابایت)" )
    storage_gb: float | None = Field( default=None, ge=0, description="‫حافظه داخلی (گیگابایت)" )
    battery_mah: float | None = Field( default=None, ge=0, description="‫باتری (میلی آمپر ساعت)" )
    screen_size_inch: float | None = Field( default=None, ge=0, description="اندازه صفحه‌نمایش (اینچ)" )
    camera_mp: float | None = Field( default=None, ge=0, description="رزولوشن دوربین اصلی (مگاپیکسل)" )
    weight_g: float | None = Field( default=None, ge=0, description="وزن دستگاه (گرم)" )

    # سایر فیلدهای مهم
    os: str | None = Field( default=None, description="‫سیستم عامل (iOS/Android/...)" )
    processor: str | None = Field( default=None, description="تراشه/پردازنده" )
    release_year: int | None = Field( default=None, ge=2000, le=2030, description="سال عرضه به بازار" )


#────────────────────────────────────────── Main Product Model ──────────────────────────────────────────


class Product( BaseModel ):
    """مدل اصلی محصول (نرمال‌شده و آماده پردازش)"""

    # ‫شناسایی
    product_id: int = Field( description="‫شناسه یکتای محصول" )
    title: str = Field( min_length=1, description="عنوان کامل محصول" )
    brand: str | None = Field( default=None, description="نام برند سازنده" )
    category: ProductCategory = Field( description="دسته‌بندی اصلی محصول" )
    url: str = Field( description="لینک مستقیم صفحه محصول" )

    # ‫قیمت و موجودی
    price: int = Field( ge=0, description="قیمت فروش نهایی (تومان)" )
    original_price: int = Field( ge=0, description="قیمت پایه قبل از تخفیف (تومان)" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="درصد تخفیف اعمال‌شده" )
    is_available: bool = Field( description="وضعیت موجودی " )
    status: ProductStatus = Field( description="‫وضعیت موجودی" )

    # ‫امتیاز
    rating: float = Field( ge=0, le=5, description="میانگین امتیاز کاربران (از ۵)" )
    rating_count: int = Field( ge=0, description="تعداد کل رأی‌دهندگان" )

    # ‫تصاویر
    image_url: str | None = Field( default=None, description="لینک تصویر اصلی محصول" )
    images: list[ str ] = Field( default_factory=list, description="لیست تمام تصاویر موجود" )

    # ‫رنگ‌ها
    colors: list[ str ] = Field( default_factory=list, description="‫رنگ‌های موجود" )

    # ‫مشخصات فنی
    specifications: ProductSpecification = Field( default_factory=ProductSpecification )

    expert_review: ExpertReview | None = Field( default=None, description="نقد تخصصی" )
    user_feedback: UserFeedback | None = Field( default=None, description="بازخورد کاربران" )

    # ‫متادیتا
    scraped_at: datetime = Field( default_factory=lambda: datetime.now( timezone.utc ) )
    updated_at: datetime = Field( default_factory=lambda: datetime.now( timezone.utc ) )

    # ‫فیلدهای محاسباتی (برای Qdrant)
    price_range: PriceRange = Field( default=PriceRange.BUDGET, description="بازه قیمتی محاسبه‌شده" )
    battery_quality: QualityLevel = Field( default=QualityLevel.UNKNOWN, description="سطح کیفی باتری" )
    camera_quality: QualityLevel = Field( default=QualityLevel.UNKNOWN, description="سطح کیفی دوربین" )
    value_for_money: QualityLevel = Field( default=QualityLevel.UNKNOWN, description="ارزش خرید نسبت به قیمت" )

    tags: list[ str ] = Field( default_factory=list, description="‫برچسب‌های استنتاجی" )

    #────────────────────────────────────────── Validators ──────────────────────────────────────────

    @field_validator( "product_id" )
    @classmethod
    def validate_product_id( cls, value: int ) -> int:
        """‫اعتبارسنجی ID محصول"""
        if value <= 0:
            raise ValueError( "‫product_id باید مثبت باشد" )
        return value

    @field_validator( "price", "original_price", mode="before" )
    @classmethod
    def convert_rial_to_toman( cls, value: int ) -> int:
        """تبدیل خودکار قیمت از ریال به تومان
        
        ‫API دیجی‌کالا قیمت‌ها را به ریال ارسال می‌کند. این validator پیش از اعتبارسنجی نهایی،
       ‫ مقدار را بر ۱۰ تقسیم صحیح می‌کند تا واحد پول پروژه (تومان) در کل لایه‌ها یکسان بماند.
        """
        return value // 10
