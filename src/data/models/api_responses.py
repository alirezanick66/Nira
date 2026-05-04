"""‫مدل‌های Pydantic برای خروجی API  دیجی‌کالا

‫این مدل‌ها دقیقاً ساختار JSON برگشتی از API رو map می‌کنن
‫فقط فیلدهای مورد نیاز رو extract می‌کنیم، بقیه ignore می‌شن
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# ==================== Product ID List API ====================


class DigikalaPager( BaseModel ):
    """‫اطلاعات صفحه"""

    current_page: int = Field( description="‫صفحه فعلی" )
    total_pages: int = Field( description="‫تعداد کل صفحات" )
    total_items: int = Field( description="‫تعداد کل محصولات" )


class DigikalaProductListItem( BaseModel ):
    """‫آیتم محصول در لیست (فقط ID)"""

    id: int = Field( description="‫شناسه محصول" )


class DigikalaProductListData( BaseModel ):
    """‫داده‌های اصلی response لیست محصولات"""

    pager: DigikalaPager
    products: list[ DigikalaProductListItem ]


class DigikalaProductListResponse( BaseModel ):
    """‫Response کامل API لیست محصولات"""

    status: int = Field( default=200 )
    data: DigikalaProductListData


# ==================== Product Detail API ====================


class DigikalaURL( BaseModel ):
    """‫ساختار URL محصول"""

    uri: str = Field( description="‫مسیر نسبی محصول" )


class DigikalaBrand( BaseModel ):
    """‫اطلاعات برند"""

    title_fa: str | None = Field( default=None, description="‫نام فارسی برند" )
    title_en: str | None = Field( default=None, description="‫نام انگلیسی برند" )


class DigikalaRating( BaseModel ):
    """‫امتیاز محصول"""

    rate: float = Field( ge=0, le=100, description="‫امتیاز از 100" )
    count: int = Field( ge=0, description="‫تعداد رای‌دهندگان" )


class DigikalaColor( BaseModel ):
    """‫رنگ محصول"""
    model_config = ConfigDict( extra="ignore" )          # نادیده گرفتن ایمن فیلدهای اضافی
    title: str


class DigikalaImages( BaseModel ):
    """تصاویر محصول — فقط تصویر اصلی"""

    model_config = ConfigDict( extra="ignore" )          # ‫← نادیده گرفتن فیلدهای اضافی مثل "list"
    webp_url: str | None = Field( default=None, description="لینک تصویر اصلی (WebP)" )

    @model_validator( mode="before" )
    @classmethod
    def _extract_main_webp_url( cls, data: object ) -> dict:
        """استخراج اولین URL از main.webp_url قبل از ساخت مدل"""
        if not isinstance( data, dict ):
            return { "webp_url": None }

        # اولویت: main.webp_url (تصویر اصلی)
        main = data.get( "main" )
        if isinstance( main, dict ):
            urls = main.get( "webp_url" )
            if isinstance( urls, list ) and urls:
                return { "webp_url": urls[ 0 ] }          # ← فقط اولین

        return { "webp_url": None }


class DigikalaPrice( BaseModel ):
    """‫قیمت محصول"""

    selling_price: int = Field( ge=0, description="‫قیمت فروش (ریال)" )
    rrp_price: int = Field( ge=0, description="‫قیمت اصلی (ریال)" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="‫درصد تخفیف" )
    is_incredible: bool = Field( default=False, description="‫شگفت‌انگیز؟" )
    is_promotion: bool = Field( default=False, description="‫تخفیف‌دار؟" )


class DigikalaProductVariant( BaseModel ):
    """‫Variant محصول (رنگ/گارانتی مختلف)"""

    id: int
    status: str = Field( description="‫marketable/stop_production/..." )
    price: DigikalaPrice
    color: DigikalaColor | None = None


class DigikalaSpecAttribute( BaseModel ):
    """‫یک ویژگی در specifications"""

    title: str = Field( description="‫عنوان ویژگی (مثلاً 'حافظه داخلی')" )
    values: list[ str ] = Field( default_factory=list, description="‫مقادیر (مثلاً ['256 گیگابایت'])" )


class DigikalaSpecification( BaseModel ):
    """‫یک دسته از مشخصات فنی"""
    model_config = ConfigDict( populate_by_name=True )          #‫فعالسازی alias

    category: str | None = Field( default=None, alias="title", description="عنوان دسته)" )          #‫api از فیلد title استفاده میکنه
    attributes: list[ DigikalaSpecAttribute ] = Field( default_factory=list )


class DigikalaExpertSectionItem( BaseModel ):
    model_config = ConfigDict( extra="ignore" )

    text: str | None = Field( default=None, description="متن بخش نقد تخصصی" )

    @field_validator( "text", mode="before" )
    @classmethod
    def _normalize_text( cls, value: object ) -> str | None:
        """‫تبدیل مقادیر نامعتبر به None"""
        if value is None or ( isinstance( value, str ) and value.strip() == "" ):
            return None
        return value if isinstance( value, str ) else str( value )


class DigikalaExpertReviewSection( BaseModel ):
    """‫یک بخش از نقد تخصصی"""
    model_config = ConfigDict( extra="ignore" )

    title: str
    sections: list[ DigikalaExpertSectionItem ] = Field( default_factory=list )


class DigikalaExpertReview( BaseModel ):
    """‫نقد تخصصی محصول"""
    model_config = ConfigDict( extra="ignore" )

    description: str = Field( default="", description="‫توضیحات اصلی" )
    review_sections: list[ DigikalaExpertReviewSection ] = Field( default_factory=list )


class DigikalaCommentsOverview( BaseModel ):
    """‫خلاصه نظرات کاربران"""

    id: int
    overview: str = Field( description="‫خلاصه کلی نظرات" )
    advantages: list[ str ] = Field( default_factory=list, description="‫مزایا از دید کاربران" )
    disadvantages: list[ str ] = Field( default_factory=list, description="‫معایب از دید کاربران" )


class DigikalaProduct( BaseModel ):
    """‫اطلاعات کامل محصول از API جزئیات"""

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
        return value          # type: ignore  # Pydantic نوع نهایی را چک می‌کند

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

    # Comments Overview (اختیاری)
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

        # ‫هر نوع دیگر (مثلاً dict خام) → اجازه به Pydantic برای اعتبارسنجی بعدی
        # ‫با type: ignore چون Pydantic در مرحله بعد نوع نهایی را چک می‌کند
        return value          # type: ignore[return-value]


class DigikalaProductDetailData( BaseModel ):
    """‫داده‌های اصلی response جزئیات محصول"""

    product: DigikalaProduct


class DigikalaProductDetailResponse( BaseModel ):
    """‫Response کامل API جزئیات محصول"""

    status: int = Field( default=200 )
    data: DigikalaProductDetailData
