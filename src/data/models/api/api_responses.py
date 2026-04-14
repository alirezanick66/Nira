"""‫مدل‌های Pydantic برای خروجی API  دیجی‌کالا

‫این مدل‌ها دقیقاً ساختار JSON برگشتی از API رو map می‌کنن
‫فقط فیلدهای مورد نیاز رو extract می‌کنیم، بقیه ignore می‌شن
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator

# ==================== Product ID List API ====================


class DigikalaPager( BaseModel ):
    """‫اطلاعات صفحه"""

    current_page: int = Field( description="‫صفحه فعلی" )
    total_pages: int = Field( description="‫تعداد کل صفحات" )
    total_items: int = Field( description="‫تعداد کل محصولات" )


class DigikaiaProductListItem( BaseModel ):
    """‫آیتم محصول در لیست (فقط ID)"""

    id: int = Field( description="‫شناسه محصول" )


class DigikaiaProductListData( BaseModel ):
    """‫داده‌های اصلی response لیست محصولات"""

    pager: DigikalaPager
    products: list[ DigikaiaProductListItem ]


class DigikaiaProductListResponse( BaseModel ):
    """‫Response کامل API لیست محصولات"""

    status: int = Field( default=200 )
    data: DigikaiaProductListData


# ==================== Product Detail API ====================


class DigikaiaURL( BaseModel ):
    """‫ساختار URL محصول"""

    uri: str = Field( description="‫مسیر نسبی محصول" )


class DigikaiaBrand( BaseModel ):
    """‫اطلاعات برند"""

    title_fa: str | None = Field( default=None, description="‫نام فارسی برند" )
    title_en: str | None = Field( default=None, description="‫نام انگلیسی برند" )


class DigikaiaRating( BaseModel ):
    """‫امتیاز محصول"""

    rate: float = Field( ge=0, le=100, description="‫امتیاز از 100" )
    count: int = Field( ge=0, description="‫تعداد رای‌دهندگان" )


class DigikaiaColor( BaseModel ):
    """‫رنگ محصول"""
    title: str


class DigikaiaImages( BaseModel ):
    """‫تصاویر محصول"""

    webp_url: list[ str ] = Field( default_factory=list )


class DigikaiaPrice( BaseModel ):
    """‫قیمت محصول"""

    selling_price: int = Field( ge=0, description="‫قیمت فروش (ریال)" )
    rrp_price: int = Field( ge=0, description="‫قیمت اصلی (ریال)" )
    discount_percent: int = Field( default=0, ge=0, le=100, description="‫درصد تخفیف" )
    is_incredible: bool = Field( default=False, description="‫شگفت‌انگیز؟" )
    is_promotion: bool = Field( default=False, description="‫تخفیف‌دار؟" )


class DigikaiaProductVariant( BaseModel ):
    """‫Variant محصول (رنگ/گارانتی مختلف)"""

    id: int
    status: str = Field( description="‫marketable/stop_production/..." )
    price: DigikaiaPrice
    color: DigikaiaColor | None = None


class DigikaiaSpecAttribute( BaseModel ):
    """‫یک ویژگی در specifications"""

    title: str = Field( description="‫عنوان ویژگی (مثلاً 'حافظه داخلی')" )
    values: list[ str ] = Field( default_factory=list, description="‫مقادیر (مثلاً ['256 گیگابایت'])" )


class DigikaiaSpecification( BaseModel ):
    """‫یک دسته از مشخصات فنی"""

    category: str | None = Field( default=None, description="‫عنوان دسته (معمولاً null)" )
    attributes: list[ DigikaiaSpecAttribute ] = Field( default_factory=list )


class DigikaiaExpertSectionItem( BaseModel ):
    model_config = ConfigDict( extra="ignore" )
    text: str | None = Field( default=None, description="متن بخش نقد تخصصی" )


class DigikaiaExpertReviewSection( BaseModel ):
    """‫یک بخش از نقد تخصصی"""

    title: str
    sections: list[ DigikaiaExpertSectionItem ] = Field( default_factory=list )


class DigikaiaExpertReview( BaseModel ):
    """‫نقد تخصصی محصول"""

    description: str = Field( default="", description="‫توضیحات اصلی" )
    review_sections: list[ DigikaiaExpertReviewSection ] = Field( default_factory=list )


class DigikaiaCommentsOverview( BaseModel ):
    """‫خلاصه نظرات کاربران"""

    id: int
    overview: str = Field( description="‫خلاصه کلی نظرات" )
    advantages: list[ str ] = Field( default_factory=list, description="‫مزایا از دید کاربران" )
    disadvantages: list[ str ] = Field( default_factory=list, description="‫معایب از دید کاربران" )


class DigikaiaProduct( BaseModel ):
    """‫اطلاعات کامل محصول از API جزئیات"""

    # اطلاعات پایه
    id: int
    title_fa: str
    title_en: str | None = None
    url: DigikaiaURL
    brand: DigikaiaBrand | None = None
    status: str = Field( description="‫marketable/stop_production/..." )

    # قیمت و موجودی (‫از default_variant)
    default_variant: DigikaiaProductVariant

    # امتیاز
    rating: DigikaiaRating

    # رنگ‌ها
    colors: list[ DigikaiaColor ] = Field( default_factory=list )

    # تصاویر
    images: DigikaiaImages

    # مشخصات فنی
    specifications: list[ DigikaiaSpecification ] = Field( default_factory=list )

    # Expert Review (اختیاری)
    expert_review: DigikaiaExpertReview | None = None

    # Comments Overview (اختیاری)
    comments_overview: DigikaiaCommentsOverview | None = None

    @field_validator( "comments_overview", mode="before" )
    @classmethod
    def _normalize_comments_overview( cls, value: object ) -> DigikaiaCommentsOverview | None:
        """‫تبدیل لیست خالی [] به None برای تحمل ناهمگونی API دیجی‌کالا"""
        # ‫لیست خالی → None
        if isinstance( value, list ) and len( value ) == 0:
            return None

        # ‫None یا از قبل معتبر → بازگرداندن مستقیم
        if value is None or isinstance( value, DigikaiaCommentsOverview ):
            return value

        # ‫هر نوع دیگر (مثلاً dict خام) → اجازه به Pydantic برای اعتبارسنجی بعدی
        # ‫با type: ignore چون Pydantic در مرحله بعد نوع نهایی را چک می‌کند
        return value          # type: ignore[return-value]


class DigikaiaProductDetailData( BaseModel ):
    """‫داده‌های اصلی response جزئیات محصول"""

    product: DigikaiaProduct


class DigikaiaProductDetailResponse( BaseModel ):
    """‫Response کامل API جزئیات محصول"""

    status: int = Field( default=200 )
    data: DigikaiaProductDetailData
