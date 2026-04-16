"""‫مدل Payload برای Qdrant

‫این مدل فقط فیلدهای ضروری برای Retrieval رو داره:
‫- فیلدهای فیلترینگ (price, ram, storage, ...)
‫- خلاصه محتوا (برای context)
‫- متادیتا (tags, quality levels)
"""

from pydantic import BaseModel, Field

from ...data.models.core.product import Product


class QdrantProductPayload( BaseModel ):
    """‫Payload محصول برای ذخیره در Qdrant

    ‫این مدل باید:
    ‫1. سبک باشه (حجم کم)
    ‫2. همه فیلدهای فیلترینگ رو داشته باشه
    ‫3. خلاصه‌ای از محتوا برای context داشته باشه
    """

    # ==================== شناسایی ====================
    product_id: int = Field( description="‫شناسه محصول" )
    title: str = Field( description="‫عنوان محصول" )
    brand: str | None = Field( default=None, description="‫برند" )
    category: str = Field( description="‫دسته‌بندی (موبایل/هدفون/...)" )

    # ==================== قیمت و موجودی ====================
    price: int = Field( ge=0, description="‫قیمت فروش (تومان)" )
    is_available: bool = Field( description="‫موجود؟" )
    has_discount: bool = Field( default=False, description="‫تخفیف‌دار؟" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="‫درصد تخفیف" )

    # ==================== مشخصات فنی نرمال شده ====================
    ram_gb: int | None = Field( default=None, ge=0, description="‫رم (GB)" )
    storage_gb: int | None = Field( default=None, ge=0, description="‫حافظه (GB)" )
    battery_mah: int | None = Field( default=None, ge=0, description="‫باتری (mAh)" )
    screen_size_inch: float | None = Field( default=None, ge=0, description="‫صفحه (inch)" )
    camera_mp: int | None = Field( default=None, ge=0, description="‫دوربین (MP)" )
    weight_g: int | None = Field( default=None, ge=0, description="‫وزن (g)" )

    # ==================== دسته‌بندی ====================
    os: str | None = Field( default=None, description="‫سیستم عامل (iOS/Android)" )
    release_year: int | None = Field( default=None, ge=2000, le=2030, description="‫سال معرفی" )
    price_range: str = Field( description="‫رنج قیمتی (budget/mid/premium/flagship)" )

    # ==================== رنگ‌ها ====================
    colors: list[ str ] = Field( default_factory=list, description="‫رنگ‌های موجود" )

    # ==================== خلاصه محتوا ====================
    expert_summary: str | None = Field( default=None, max_length=200, description="‫خلاصه نقد تخصصی" )

    # ==================== بازخورد کاربران ====================
    user_advantages: list[ str ] = Field( default_factory=list, description="‫مزایا از دید کاربران" )
    user_disadvantages: list[ str ] = Field( default_factory=list, description="‫معایب از دید کاربران" )

    # ==================== امتیاز ====================
    rating: float = Field( ge=0, le=5, description="‫امتیاز (0-5)" )
    rating_count: int = Field( ge=0, description="‫تعداد رای‌دهندگان" )

    # ==================== برچسب‌ها و کیفیت ====================
    tags: list[ str ] = Field( default_factory=list, description="‫برچسب‌های استنتاجی" )
    battery_quality: str = Field( default="unknown", description="‫کیفیت باتری" )
    camera_quality: str = Field( default="unknown", description="‫کیفیت دوربین" )
    value_for_money: str = Field( default="average", description="‫ارزش خرید" )

    search_text: str = Field( description="متن ترکیسی برای بردارسازی (عنوان + خلاصه + مزایا)" )

    @classmethod
    def from_product( cls, product: Product ) -> "QdrantProductPayload":
        """‫تبدیل Product به QdrantProductPayload

        Args:
            product: مدل Product نرمال‌شده

        Returns:
            QdrantProductPayload آماده برای ذخیره در Qdrant
        """
        # ‫خلاصه expert review
        expert_summary = None
        if product.expert_review:
            expert_summary = product.expert_review.get_summary( max_length=200 )

        # ‫مزایا/معایب کاربران
        user_advantages = []
        user_disadvantages = []
        if product.user_feedback:
            user_advantages = product.user_feedback.advantages
            user_disadvantages = product.user_feedback.disadvantages

        # ‫متن جستجو
        text_parts = [ product.title ]
        if product.expert_review: text_parts.append( product.expert_review.get_summary() )
        if product.user_feedback: text_parts.extend( product.user_feedback.advantages[ :3 ] )
        search_text = " | ".join( filter( None, text_parts ) )

        return cls(
            product_id=product.product_id,
            title=product.title,
            brand=product.brand,
            category=product.category.value,
          # قیمت
            price=product.price,
            discount_percent=product.discount_percent,
            is_available=product.is_available,
            has_discount=product.discount_percent > 0,
          # امتیاز
            rating=product.rating,
            rating_count=product.rating_count,
          # مشخصات
            ram_gb=product.specifications.ram_gb,
            storage_gb=product.specifications.storage_gb,
            battery_mah=product.specifications.battery_mah,
            screen_size_inch=product.specifications.screen_size_inch,
            camera_mp=product.specifications.camera_mp,
            weight_g=product.specifications.weight_g,
          # دسته‌بندی
            os=product.specifications.os,
            release_year=product.specifications.release_year,
            price_range=product.price_range.value if product.price_range else "mid",
          # سایر
            colors=product.colors,
            expert_summary=expert_summary,
            user_advantages=user_advantages,
            user_disadvantages=user_disadvantages,
            tags=product.tags,
            battery_quality=product.battery_quality.value,
            camera_quality=product.camera_quality.value,
            value_for_money=product.value_for_money.value,
            search_text=search_text,
        )

    def to_dict( self ) -> dict:
        """‫تبدیل به dictionary برای Qdrant"""
        return self.model_dump( exclude_none=False )
