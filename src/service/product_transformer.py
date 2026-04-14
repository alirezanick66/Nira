"""‫سرویس تبدیل API Response به Product Model

‫این ماژول مسئول تبدیل داده‌های خام API دیجی‌کالا به مدل Product نرمال‌شده هست
"""

from src.data.models.core.product import ExpertReview, Product, ProductSpecification, ReviewSectionItem, UserFeedback
from src.data.models.core.product import ProductCategory, ProductStatus
from src.data.models.api.api_responses import DigikaiaProduct
from src.utils.spec_normalizer import SpecNormalizer


class ProductTransformer:
    """‫تبدیل‌گر API Response به Product Model"""

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
        """‫نگاشت status API به ProductStatus enum

        Args:
            status: وضعیت از API (marketable, stop_production, ...)

        Returns:
            ProductStatus enum
        """
        status_map = {
            "marketable": ProductStatus.MARKETABLE,
            "out_of_stock": ProductStatus.OUT_OF_STOCK,
        }

        return status_map.get( status, ProductStatus.OUT_OF_STOCK )

    @staticmethod
    def _serialize_specs( specs: list ) -> list[ dict ]:
        """تبدیل DigikaiaSpecification → dict"""
        return [ spec.model_dump() for spec in specs ]

    @classmethod
    def transform( cls, api_product: DigikaiaProduct ) -> Product:
        """‫تبدیل DigikaiaProduct به Product

        Args:
            api_product: داده خام از API دیجی‌کالا

        Returns:
            Product نرمال‌شده و آماده ذخیره

        Example:
            >>> api_response = DigikaiaProductDetailResponse(**api_data)
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
        image_url = api_product.images.webp_url[ 0 ] if api_product.images.webp_url else None

        # ‫ساخت Product
        product = Product(
          # ‫شناسایی
            product_id=api_product.id,
            title=api_product.title_fa,
            brand=api_product.brand.title_fa if api_product.brand else None,
            category=cls._determine_category( api_product.title_fa ),
            url=api_product.url.uri,
          # ‫قیمت (تبدیل خودکار ریال → تومان در validator)
            price=api_product.default_variant.price.selling_price,
            original_price=api_product.default_variant.price.rrp_price,
            discount_percent=api_product.default_variant.price.discount_percent,
          # ‫موجودی
            is_available=api_product.status == "marketable",
            status=cls._map_status( api_product.status ),
          # ‫امتیاز (تبدیل 0-100 → 0-5)
            rating=api_product.rating.rate / 20,
            rating_count=api_product.rating.count,
          # ‫تصاویر و رنگ‌ها
            image_url=image_url,
            colors=colors,
          # ‫مشخصات
            specifications=specifications,
            expert_review=expert_review,
            user_feedback=user_feedback,
        )

        return product
