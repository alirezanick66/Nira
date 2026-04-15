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
    model_config = ConfigDict( extra="ignore" )          # نادیده گرفتن ایمن فیلدهای اضافی
    title: str


class DigikaiaImages( BaseModel ):
    """‫تصاویر محصول"""

    webp_url: list[ str ] = Field( default_factory=list )

    @field_validator( "webp_url", mode="before" )
    @classmethod
    def _extract_webp_url( cls, value: object ) -> list[ str ]:
        """‫استخراج لیست URL از ساختار تودرتوی API"""
        if isinstance( value, dict ):
            # ‫حالت ۱: {"main": {"webp_url": [...]}}
            if "main" in value and isinstance( value[ "main" ], dict ):
                return value[ "main" ].get( "webp_url", [] )
            # ‫حالت ۲: {"webp_url": [...]} (مستقیم)
            if "webp_url" in value and isinstance( value[ "webp_url" ], list ):
                return value[ "webp_url" ]
        # ‫حالت ۳: لیست مستقیم یا مقدار نامعتبر
        return value if isinstance( value, list ) else []


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
    model_config = ConfigDict( populate_by_name=True )          #‫فعالسازی alias

    category: str | None = Field( default=None, alias="title", description="عنوان دسته)" )          #‫api از فیلد title استفاده میکنه
    attributes: list[ DigikaiaSpecAttribute ] = Field( default_factory=list )


class DigikaiaExpertSectionItem( BaseModel ):
    model_config = ConfigDict( extra="ignore" )

    text: str | None = Field( default=None, description="متن بخش نقد تخصصی" )

    @field_validator( "text", mode="before" )
    @classmethod
    def _normalize_text( cls, value: object ) -> str | None:
        """‫تبدیل مقادیر نامعتبر به None"""
        if value is None or ( isinstance( value, str ) and value.strip() == "" ):
            return None
        return value if isinstance( value, str ) else str( value )


class DigikaiaExpertReviewSection( BaseModel ):
    """‫یک بخش از نقد تخصصی"""
    model_config = ConfigDict( extra="ignore" )

    title: str
    sections: list[ DigikaiaExpertSectionItem ] = Field( default_factory=list )


class DigikaiaExpertReview( BaseModel ):
    """‫نقد تخصصی محصول"""
    model_config = ConfigDict( extra="ignore" )

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
    default_variant: DigikaiaProductVariant | None = None

    @field_validator( "default_variant", mode="before" )
    @classmethod
    def _normalize_default_variant( cls, value: object ) -> DigikaiaProductVariant | None:
        """‫تبدیل لیست خالی [] به None برای محصولات بدون واریانت"""
        if isinstance( value, list ) and len( value ) == 0:
            return None
        return value          # type: ignore  # Pydantic نوع نهایی را چک می‌کند

    # امتیاز
    rating: DigikaiaRating

    # رنگ‌ها
    colors: list[ DigikaiaColor ] = Field( default_factory=list )

    # تصاویر
    images: DigikaiaImages

    # مشخصات فنی
    specifications: list[ DigikaiaSpecification ] = Field( default_factory=list )

    # Expert Review (اختیاری)
    expert_review: DigikaiaExpertReview | None = Field(
        default=None,
        alias="expert_reviews"          # ‫← API می‌فرستد expert_reviews، ما داخلی expert_review صدا می‌زنیم
    )

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
