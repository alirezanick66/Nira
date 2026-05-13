"""‫مدل‌های Pydantic برای نگاشت و اعتبارسنجی خروجی API دیجی‌کالا
‫این لایه صرفاً مسئول تبدیل JSON خام API به اشیای تایپ‌شده است.
‫فیلدهای اضافی توسط ConfigDict نادیده گرفته می‌شوند.
"""

#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# ────────────────────────────────────────── Product ID List API ──────────────────────────────────────────


class DigikalaPager( BaseModel ):
    """ ‫اطلاعات صفحه‌بندی پاسخ API"""

    current_page: int = Field( description="شماره صفحه فعلی" )
    total_pages: int = Field( description="تعداد کل صفحات" )
    total_items: int = Field( description="تعداد کل آیتم‌ها" )


class DigikalaProductListItem( BaseModel ):
    """آیتم محصول در لیست (فقط شامل شناسه)"""
    id: int = Field( description="شناسه عددی محصول" )


class DigikalaProductListData( BaseModel ):
    """بدنه اصلی پاسخ لیست محصولات"""
    pager: DigikalaPager
    products: list[ DigikalaProductListItem ]


class DigikalaProductListResponse( BaseModel ):
    """‫ساختار کامل پاسخ API لیست محصولات"""
    status: int = Field( default=200, description="کد وضعیت پاسخ" )
    data: DigikalaProductListData


# ────────────────────────────────────────── Product Detail API ──────────────────────────────────────────


class DigikalaURL( BaseModel ):
    """ ‫ساختار آدرس (URL) محصول"""

    uri: str = Field( description="لینک آدرس محصول" )


class DigikalaBrand( BaseModel ):
    """‫اطلاعات برند"""

    title_fa: str | None = Field( default=None, description="‫نام فارسی برند" )
    title_en: str | None = Field( default=None, description="‫نام انگلیسی برند" )


class DigikalaRating( BaseModel ):
    """‫امتیاز محصول"""

    rate: float = Field( ge=0, le=100, description="میانگین امتیاز از ۱۰۰" )
    count: int = Field( ge=0, description="تعداد کل رای‌دهندگان" )


class DigikalaColor( BaseModel ):
    """‫رنگ محصول"""
    model_config = ConfigDict( extra="ignore" )          # نادیده گرفتن ایمن فیلدهای اضافی
    title: str


class DigikalaImages( BaseModel ):
    """تصاویر محصول (استخراج خودکار تصویر اصلی)"""

    model_config = ConfigDict( extra="ignore" )          # ‫← نادیده گرفتن فیلدهای اضافی مثل "list"
    webp_url: str | None = Field( default=None, description="‫لینک تصویر اصلی (WebP)" )

    @model_validator( mode="before" )
    @classmethod
    def _extract_main_webp_url( cls, data: object ) -> dict:
        """‫استخراج اولین URL از main.webp_url قبل از ساخت مدل"""
        if not isinstance( data, dict ):
            return { "webp_url": None }

        main = data.get( "main" )
        if isinstance( main, dict ):
            urls = main.get( "webp_url" )
            if isinstance( urls, list ) and urls:
                return { "webp_url": urls[ 0 ] }          # ← فقط اولین

        return { "webp_url": None }


class DigikalaPrice( BaseModel ):
    """ساختار قیمت و تخفیف (بر حسب ریال)"""
    selling_price: int = Field( ge=0, description="قیمت فروش نهایی" )
    rrp_price: int = Field( ge=0, description="قیمت پایه قبل از تخفیف" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="درصد تخفیف" )
    is_incredible: bool = Field( default=False, description="وضعیت شگفت‌انگیز" )
    is_promotion: bool = Field( default=False, description="وضعیت تخفیف‌دار بودن" )


class DigikalaProductVariant( BaseModel ):
    """ محصول (رنگ/گارانتی مختلف)"""

    id: int
    status: str = Field( description="‫marketable/stop_production/..." )
    price: DigikalaPrice
    color: DigikalaColor | None = None


class DigikalaSpecAttribute( BaseModel ):
    """‫ویژگی در specifications"""

    title: str = Field( description="‫عنوان ویژگی (مثلاً 'حافظه داخلی')" )
    values: list[ str ] = Field( default_factory=list, description="‫مقادیر (مثلاً ['256 گیگابایت'])" )


class DigikalaSpecification( BaseModel ):
    """دسته‌بندی مشخصات فنی"""
    model_config = ConfigDict( populate_by_name=True )          #‫فعالسازی alias

    category: str | None = Field( default=None, alias="title", description="عنوان دسته)" )          #‫api از فیلد title استفاده میکنه
    attributes: list[ DigikalaSpecAttribute ] = Field( default_factory=list )


class DigikalaExpertSectionItem( BaseModel ):
    """آیتم متنی در بخش نقد تخصصی"""
    model_config = ConfigDict( extra="ignore" )

    text: str | None = Field( default=None, description="متن بخش نقد تخصصی" )

    @field_validator( "text", mode="before" )
    @classmethod
    def _normalize_text( cls, value: object ) -> str | None:
        """تبدیل مقادیر خالی یا نامعتبر به None"""
        if value is None or ( isinstance( value, str ) and value.strip() == "" ):
            return None
        return value if isinstance( value, str ) else str( value )


class DigikalaExpertReviewSection( BaseModel ):
    """‫یک بخش از نقد تخصصی"""
    model_config = ConfigDict( extra="ignore" )

    title: str
    sections: list[ DigikalaExpertSectionItem ] = Field( default_factory=list )


class DigikalaExpertReview( BaseModel ):
    """ساختار کامل نقد تخصصی محصول"""
    model_config = ConfigDict( extra="ignore" )

    description: str = Field( default="", description="توضیحات کلی نقد" )
    review_sections: list[ DigikalaExpertReviewSection ] = Field( default_factory=list )


class DigikalaCommentsOverview( BaseModel ):
    """خلاصه نظرات و بازخوردهای کاربران"""

    id: int
    overview: str = Field( description="جمع‌بندی کلی نظرات" )
    advantages: list[ str ] = Field( default_factory=list, description="لیست مزایا از دید کاربران" )
    disadvantages: list[ str ] = Field( default_factory=list, description="لیست معایب از دید کاربران" )


class DigikalaProduct( BaseModel ):
    """‫اطلاعات کامل محصول دریافتی از API جزئیات"""

    # اطلاعات پایه
    id: int
    title_fa: str
    title_en: str | None = None
    url: DigikalaURL
    brand: DigikalaBrand | None = None
    status: str = Field( description="‫marketable/stop_production/..." )

    # قیمت و موجودی (‫از default_variant)
    default_variant: DigikalaProductVariant | None = None

    @field_validator( "default_variant", mode="before" )
    @classmethod
    def _normalize_default_variant( cls, value: object ) -> DigikalaProductVariant | None:
        """‫تبدیل لیست خالی [] به None برای محصولات بدون واریانت"""
        if isinstance( value, list ) and len( value ) == 0:
            return None
        return value          # type: ignore  # ‫Pydantic نوع نهایی را چک می‌کند

    # امتیاز
    rating: DigikalaRating

    # رنگ‌ها
    colors: list[ DigikalaColor ] = Field( default_factory=list )

    # تصاویر
    images: DigikalaImages

    # مشخصات فنی
    specifications: list[ DigikalaSpecification ] = Field( default_factory=list )

    # Expert Review (اختیاری)
    expert_review: DigikalaExpertReview | None = Field(
        default=None,
        alias="expert_reviews"          # ‫← API می‌فرستد expert_reviews، ما داخلی expert_review صدا می‌زنیم
    )

    # نظرات کاربران (اختیاری)
    comments_overview: DigikalaCommentsOverview | None = None

    @field_validator( "comments_overview", mode="before" )
    @classmethod
    def _normalize_comments_overview( cls, value: object ) -> DigikalaCommentsOverview | None:
        """‫تبدیل لیست خالی [] به None برای تحمل ناهمگونی API دیجی‌کالا"""
        # ‫لیست خالی → None
        if isinstance( value, list ) and len( value ) == 0:
            return None

        # ‫None یا از قبل معتبر → بازگرداندن مستقیم
        if value is None or isinstance( value, DigikalaCommentsOverview ):
            return value

        return value          # type: ignore # ‫Pydantic نوع نهایی را چک می‌کند


class DigikalaProductDetailData( BaseModel ):
    """بدنه اصلی پاسخ API جزئیات محصول"""

    product: DigikalaProduct


class DigikalaProductDetailResponse( BaseModel ):
    """ ‫ساختار کامل پاسخ API جزئیات محصول"""

    status: int = Field( default=200 )
    data: DigikalaProductDetailData
