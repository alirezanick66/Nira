"""‫مدل محصول نرمال‌شده برای استفاده داخلی

‫این مدل ساختار تمیز و استانداردی رو ارائه می‌ده که:
‫- مستقل از ساختار API دیجی‌کالا
‫- آماده ذخیره در PostgreSQL
‫- آماده تبدیل به Qdrant Payload
"""

#==================== Imports ====================
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


#==================== Enum Class ====================
class ProductCategory( str, Enum ):
    """‫دسته‌بندی محصولات"""

    MOBILE = "موبایل"
    HEADPHONE = "هدفون"
    EARPHONE = "هندزفری"


class ProductStatus( str, Enum ):
    """‫وضعیت موجودی محصول"""

    MARKETABLE = "marketable"          # موجود
    OUT_OF_STOCK = "out_of_stock"          # ناموجود


class PriceRange( str, Enum ):
    """‫رنج قیمتی محصول"""

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


# ==================== Nested Models ====================


class NormalizedSpec( BaseModel ):
    """‫یک مشخصه نرمال‌شده (برای ذخیره در product_specifications)"""

    spec_category: str = Field( description="‫دسته مشخصه (processor/memory/camera/...)" )
    spec_key: str = Field( description="‫کلید مشخصه (ram/storage/battery/...)" )
    spec_value_text: str = Field( description="‫مقدار متنی ('8 گیگابایت')" )
    spec_value_numeric: float | None = Field( default=None, description="‫مقدار عددی (8)" )
    spec_unit: str | None = Field( default=None, description="‫واحد (GB/mAh/MP/...)" )


class ExpertReview( BaseModel ):
    """‫نقد تخصصی"""

    description: str = Field( description="‫توضیحات اصلی" )
    sections: list[ dict ] = Field( default_factory=list, description="‫بخش‌های نقد (JSON)" )

    def get_summary( self, max_length: int = 500 ) -> str:
        """‫دریافت خلاصه توضیحات"""
        if len( self.description ) <= max_length:
            return self.description
        return self.description[ :max_length ] + "..."


class UserFeedback( BaseModel ):
    """‫بازخورد کاربران (خلاصه‌شده)"""

    overview: str = Field( description="‫خلاصه کلی نظرات" )
    advantages: list[ str ] = Field( default_factory=list, description="‫مزایا" )
    disadvantages: list[ str ] = Field( default_factory=list, description="‫معایب" )

    def get_summary( self, max_length: int = 300 ) -> str:
        """‫دریافت خلاصه overview"""
        if len( self.overview ) <= max_length:
            return self.overview
        return self.overview[ :max_length ] + "..."


class ProductSpecification( BaseModel ):
    """‫مشخصات فنی کامل محصول (برای ذخیره در JSON)"""

    # مشخصات خام
    raw_specifications: list[ dict ] = Field( default_factory=list, description="‫specifications خام API" )

    # مشخصات نرمال‌شده (فیلدهای کلیدی)
    ram_gb: int | None = Field( default=None, ge=0, description="‫رم (گیگابایت)" )
    storage_gb: int | None = Field( default=None, ge=0, description="‫حافظه داخلی (گیگابایت)" )
    battery_mah: int | None = Field( default=None, ge=0, description="‫باتری (میلی آمپر ساعت)" )
    screen_size_inch: float | None = Field( default=None, ge=0, description="‫اندازه صفحه (اینچ)" )
    camera_mp: int | None = Field( default=None, ge=0, description="‫دوربین اصلی (مگاپیکسل)" )
    weight_g: int | None = Field( default=None, ge=0, description="‫وزن (گرم)" )

    # سایر فیلدهای مهم
    os: str | None = Field( default=None, description="‫سیستم عامل (iOS/Android/...)" )
    processor: str | None = Field( default=None, description="‫پردازنده" )
    release_year: int | None = Field( default=None, ge=2000, le=2030, description="‫سال معرفی" )


# ==================== Main Product Model ====================


class Product( BaseModel ):
    """‫مدل اصلی محصول (نرمال‌شده)"""

    # ‫شناسایی
    product_id: int = Field( description="‫شناسه عددی محصول" )
    title: str = Field( min_length=1, description="‫عنوان محصول" )
    brand: str | None = Field( default=None, description="‫برند" )
    category: ProductCategory = Field( description="‫دسته‌بندی" )
    url: str = Field( description="‫لینک محصول" )

    # ‫قیمت و موجودی
    price: int = Field( ge=0, description="‫قیمت فروش (تومان)" )
    original_price: int = Field( ge=0, description="‫قیمت اصلی (تومان)" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="‫درصد تخفیف" )
    is_available: bool = Field( description="‫موجود؟" )
    status: ProductStatus = Field( description="‫وضعیت موجودی" )

    # ‫امتیاز
    rating: float = Field( ge=0, le=5, description="‫امتیاز (0-5)" )
    rating_count: int = Field( ge=0, description="‫تعداد رای‌دهندگان" )

    # ‫تصاویر
    image_url: str | None = Field( default=None, description="‫تصویر اصلی" )
    images: list[ str ] = Field( default_factory=list, description="‫لیست تمام تصاویر" )

    # ‫رنگ‌ها
    colors: list[ str ] = Field( default_factory=list, description="‫رنگ‌های موجود" )

    # ‫مشخصات فنی
    specifications: ProductSpecification = Field( default_factory=ProductSpecification )

    # ‫نقد تخصصی
    expert_review: ExpertReview | None = Field( default=None )

    # ‫بازخورد کاربران
    user_feedback: UserFeedback | None = Field( default=None )

    # ‫متادیتا
    scraped_at: datetime = Field( default_factory=datetime.utcnow, description="‫زمان استخراج" )
    updated_at: datetime = Field( default_factory=datetime.utcnow, description="‫آخرین به‌روزرسانی" )

    # ‫فیلدهای محاسباتی (برای Qdrant)
    price_range: PriceRange | None = Field( default=None )
    battery_quality: QualityLevel = Field( default=QualityLevel.UNKNOWN )
    camera_quality: QualityLevel = Field( default=QualityLevel.UNKNOWN )
    value_for_money: QualityLevel = Field( default=QualityLevel.UNKNOWN )
    tags: list[ str ] = Field( default_factory=list, description="‫برچسب‌های استنتاجی" )

    # ==================== اعتبارسنجی فیلدها ====================

    @field_validator( "product_id" )
    @classmethod
    def validate_product_id( cls, value: int ) -> int:
        """‫اعتبارسنجی ID محصول"""
        if value <= 0:
            raise ValueError( "‫product_id باید مثبت باشد" )
        return value

    @field_validator( "price", "original_price", mode="before" )
    @classmethod
    def convert_to_toman( cls, value: int ) -> int:
        """
        ‫تبدیل ریال به تومان 
         ‫API دیجی‌کالا همیشه قیمت رو به ریال برمی‌گردونه
        """
        return value // 10
