"""‫سرویس تبدیل API Response به Product Model

‫این ماژول مسئول تبدیل داده‌های خام API دیجی‌کالا به مدل Product نرمال‌شده هست
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
import re

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.data.models.product import ( ExpertReview, Product, ProductSpecification, ReviewSectionItem, UserFeedback, ProductCategory,
                                      ProductStatus )
from src.data.models.api_responses import DigikalaProduct, DigikalaSpecification
from src.utils.spec_normalizer import SpecNormalizer


class ProductTransformer:
    """‫تبدیل‌گر API Response به Product Model"""

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    @classmethod
    def transform( cls, api_product: DigikalaProduct ) -> Product:
        """‫تبدیل DigikalaProduct به Product

        Args:
            api_product:‫ داده خام از API دیجی‌کالا

        Returns:
            ‫Product نرمال‌شده و آماده ذخیره

        Example:
            >>> api_response = DigikalaProductDetailResponse(**api_data)
            >>> api_product = api_response.data.product
            >>> product = ProductTransformer.transform(api_product)
        """

        # ‫استخراج مشخصات فنی
        normalized_specs = SpecNormalizer.extract_specifications( cls._serialize_specs( api_product.specifications ) )

        # ‫ساخت ProductSpecification
        specifications = ProductSpecification( **normalized_specs )

        # ‫استخراج Expert Review
        expert_review = None
        if api_product.expert_review:
            expert_review = ExpertReview( description=api_product.expert_review.description,
                                          sections=[
                                              ReviewSectionItem( text=item.text )
                                              for review_section in api_product.expert_review.review_sections
                                              for item in review_section.sections
                                          ] )

        # ‫استخراج User Feedback
        user_feedback = None
        if api_product.comments_overview:
            user_feedback = UserFeedback(
                overview=api_product.comments_overview.overview,
                advantages=api_product.comments_overview.advantages,
                disadvantages=api_product.comments_overview.disadvantages,
            )

        # ‫استخراج رنگ‌ها (فقط title)
        colors = [ color.title for color in api_product.colors ]

        # ‫استخراج تصویر اصلی
        image_url = api_product.images.webp_url

        # استخراج قیمت با چک کردن وجود واریانت
        price = 0
        original_price = 0
        discount_percent = 0

        if api_product.default_variant:
            price = api_product.default_variant.price.selling_price
            original_price = api_product.default_variant.price.rrp_price
            discount_percent = api_product.default_variant.price.discount_percent

        # ‫پارس دوربین و تزریق به مشخصات (بدون تغییر اسکیما)
        camera_meta = cls._parse_camera_specs( specifications.raw_specifications )
        specifications._camera_meta = camera_meta          # type: ignore
        camera_mp = camera_meta.get( "camera_mp" )
        if specifications.camera_mp is None and isinstance( camera_mp, ( int, float ) ):
            specifications.camera_mp = float( camera_mp )

        # ‫ساخت Product
        product = Product(
          # ‫شناسایی
            product_id=api_product.id,
            title=api_product.title_fa,
            brand=api_product.brand.title_fa if api_product.brand else None,
            category=cls._determine_category( api_product.title_fa ),
            url=api_product.url.uri,
          # ‫قیمت (تبدیل خودکار ریال → تومان در validator)
            price=price,
            original_price=original_price,
            discount_percent=discount_percent,
          # ‫موجودی
            is_available=api_product.status == "marketable",
            status=cls._map_status( api_product.status ),
          # ‫امتیاز (تبدیل 0-100 → 0-5)
            rating=api_product.rating.rate / 20,
            rating_count=api_product.rating.count,
          # ‫تصاویر و رنگ‌ها
            image_url=image_url,
          # images=api_product.images.webp_url,
            colors=colors,
          # ‫مشخصات
            specifications=specifications,
            expert_review=expert_review,
            user_feedback=user_feedback,
        )

        return product

    #────────────────────────────────────────── Private methods ──────────────────────────────────────────
    @staticmethod
    def _determine_category( title: str ) -> ProductCategory:
        """‫تشخیص category از عنوان محصول

        Args:
            title: عنوان محصول

        Returns:
            ProductCategory enum
        """
        title_lower = title.lower()

        if "موبایل" in title_lower or "گوشی" in title_lower or "phone" in title_lower:
            return ProductCategory.MOBILE
        elif "هدفون" in title_lower or "headphone" in title_lower:
            return ProductCategory.HEADPHONE
        elif "هندزفری" in title_lower or "earphone" in title_lower or "ایرفون" in title_lower:
            return ProductCategory.EARPHONE

        # ‫پیش‌فرض
        return ProductCategory.MOBILE

    @staticmethod
    def _map_status( status: str ) -> ProductStatus:
        """‫نگاشت status API به ‫ProductStatus enum

        Args:
            status: ‫وضعیت از API (marketable, stop_production, ...)

        Returns:
            ProductStatus enum
        """
        status_map = {
            "marketable": ProductStatus.MARKETABLE,
            "out_of_stock": ProductStatus.OUT_OF_STOCK,
        }

        return status_map.get( status, ProductStatus.OUT_OF_STOCK )

    @staticmethod
    def _parse_camera_specs( raw_specs: list[ dict[ str, object ] ] ) -> dict[ str, object ]:
        """استخراج و پارس مشخصات دوربین از داده‌های خام API

        Args:
            ‫raw_specs: لیست گروه‌های مشخصات فنی دریافتی از API

        Returns:
           ‫ دیکشنری شامل: camera_mp, main_camera_mp, has_ultrawide, video_4k, camera_summary
        """
        mp_pattern = re.compile( r'(\d+)\s*(?:مگاپیکسل|MP)', re.IGNORECASE )
        all_attrs: list[ tuple[ str, str ] ] = []

        for group in raw_specs:
            if not isinstance( group, dict ): continue
            attrs = group.get( "attributes" )
            if isinstance( attrs, list ):
                for attr in attrs:
                    if isinstance( attr, dict ):
                        title = str( attr.get( "title", "" ) ).strip()
                        values = attr.get( "values", [] )
                        val_text = " ".join( str( v ) for v in values if isinstance( v, ( str, int, float ) ) )
                        if title and val_text: all_attrs.append( ( title, val_text ) )

        main_mp: int | None = None
        has_ultrawide = False
        video_4k = False
        summary_parts: list[ str ] = []

        for title, val in all_attrs:
            if "رزولوشن دوربین اصلی" in title:
                match = mp_pattern.search( val )
                if match:
                    main_mp = int( match.group( 1 ) )
                    summary_parts.append( f"{main_mp}MP اصلی" )

            if "نوع لنز دوربین" in title or "لنز دوم" in title:
                if any( kw in val.lower() for kw in ( "فوق عریض", "اولترا واید", "ultrawide", "wide" ) ):
                    has_ultrawide = True

            if "رزولوشن فیلمبرداری" in title or "فیلمبرداری" in title:
                if "4k" in val.lower() or "۴k" in val: video_4k = True

            if "رزولوشن دوربین سلفی" in title:
                match = mp_pattern.search( val )
                if match: summary_parts.append( f"سلفی {match.group(1)}MP" )

            if "مشخصات دوربین" in title or "فیلمبرداری" in title:
                if any( kw in val for kw in ( "لرزشگیر", "OIS" ) ): summary_parts.append( "لرزشگیر" )
                if any( kw in val.lower() for kw in ( "dolby vision", "hdr" ) ): summary_parts.append( "HDR" )

        return {
            "camera_mp": main_mp,
            "main_camera_mp": main_mp,
            "has_ultrawide": has_ultrawide,
            "video_4k": video_4k,
            "camera_summary": " | ".join( summary_parts ) or None,
        }

    @staticmethod
    def _serialize_specs( specs: list[ DigikalaSpecification ] ) -> list[ dict[ str, object ] ]:
        """‫تبدیل DigikalaSpecification → dict"""
        return [ spec.model_dump() for spec in specs ]
