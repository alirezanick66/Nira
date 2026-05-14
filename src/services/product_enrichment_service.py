"""‫سرویس غنی‌سازی محصول (Product Enrichment)

‫این ماژول مسئول تحلیل و استنتاج اطلاعات اضافی از محصول هست:
‫- محاسبه price_range
‫- استنتاج ‫quality levels (battery, camera, value_for_money)
‫- تولید tags
"""
#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.data.models.product import PriceRange, Product, QualityLevel


class ProductEnrichmentService:
    """‫سرویس غنی‌سازی محصول

    ‫این کلاس منطق تحلیل رو از مدل Product جدا می‌کنه
    """
    #────────────────────────────────────────── Public Methods ──────────────────────────────────────────
    @classmethod
    def enrich_product( cls, product: Product ) -> Product:
        """‫غنی‌سازی کامل محصول

        ‫این متد همه فیلدهای محاسباتی رو پر می‌کنه:
        ‫- price_range
        ‫- battery_quality
        ‫- camera_quality
        ‫- value_for_money
        ‫- tags

        Args:
            product: مدل نرمال‌شدهٔ محصول دریافتی از لایهٔ پردازش

        Returns:
           ‫ همون Product با فیلدهای غنی‌شده
        """
        # ‫محاسبه price_range
        product.price_range = cls._calculate_price_range( product.price )

        # ‫استنتاج quality levels
        product.battery_quality = cls._infer_battery_quality( product )
        product.camera_quality = cls._infer_camera_quality( product )
        product.value_for_money = cls._infer_value_for_money( product )

        # ‫تولید tags
        product.tags = cls._generate_tags( product )

        return product

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    @staticmethod
    def _calculate_price_range( price: int ) -> PriceRange:
        """‫محاسبه رنج قیمتی بر اساس قیمت (تومان)

        Args:
            price: قیمت به تومان

        Returns:
            PriceRange enum
        """
        if price < 10_000_000:
            return PriceRange.BUDGET
        elif price < 30_000_000:
            return PriceRange.MID
        elif price < 60_000_000:
            return PriceRange.PREMIUM
        else:
            return PriceRange.FLAGSHIP

    @staticmethod
    def _infer_battery_quality( product: Product ) -> QualityLevel:
        """‫استنتاج کیفیت باتری

        ‫اولویت:
        ‫1. از user_feedback (اگه کاربران نظر دادن)
        ‫2. از مشخصات فنی (battery_mah)

        Args:
            product: مدل Product

        Returns:
            QualityLevel enum
        """
        # ‫چک کردن user_feedback
        if product.user_feedback:
            advantages = product.user_feedback.advantages
            disadvantages = product.user_feedback.disadvantages

            # ‫اگه در مزایا ذکر شده
            if any( "باتری" in adv or "شارژ" in adv for adv in advantages ):
                return QualityLevel.EXCELLENT

            # ‫اگه در معایب ذکر شده
            if any( "باتری" in dis or "شارژ" in dis for dis in disadvantages ):
                return QualityLevel.POOR

        # ‫اگه user_feedback نداریم یا ذکر نشده، از specs استفاده کن
        battery_mah = product.specifications.battery_mah
        if not battery_mah:
            return QualityLevel.UNKNOWN

        if battery_mah >= 5000:
            return QualityLevel.EXCELLENT
        elif battery_mah >= 4000:
            return QualityLevel.GOOD
        elif battery_mah >= 3000:
            return QualityLevel.AVERAGE
        else:
            return QualityLevel.POOR

    @staticmethod
    def _infer_camera_quality( product: Product ) -> QualityLevel:
        """‫استنتاج کیفیت دوربین

        ‫اولویت:
        ‫1. از user_feedback
        ‫2. از مشخصات فنی (camera_mp)

        Args:
            product: مدل Product

        Returns:
            QualityLevel enum
        """
        # ‫چک کردن user_feedback
        if product.user_feedback:
            advantages = product.user_feedback.advantages
            disadvantages = product.user_feedback.disadvantages

            if any( "دوربین" in adv or "عکس" in adv or "فیلم" in adv for adv in advantages ):
                return QualityLevel.EXCELLENT

            if any( "دوربین" in dis or "عکس" in dis or "فیلم" in dis for dis in disadvantages ):
                return QualityLevel.POOR

        # ‫از specs
        camera_mp = product.specifications.camera_mp
        if not camera_mp:
            return QualityLevel.UNKNOWN

        if camera_mp >= 48:
            return QualityLevel.EXCELLENT
        elif camera_mp >= 12:
            return QualityLevel.GOOD
        else:
            return QualityLevel.AVERAGE

    @staticmethod
    def _infer_value_for_money( product: Product ) -> QualityLevel:
        """‫استنتاج ارزش خرید (value for money)

        ‫بر اساس user_feedback

        Args:
            product: مدل Product

        Returns:
            QualityLevel enum
        """
        if not product.user_feedback:
            return QualityLevel.AVERAGE

        advantages = product.user_feedback.advantages
        disadvantages = product.user_feedback.disadvantages

        # ‫قیمت در مزایا
        if any( "قیمت" in adv or "ارزان" in adv or "مناسب" in adv for adv in advantages ):
            return QualityLevel.GOOD

        # ‫قیمت در معایب
        if any( "قیمت" in dis or "گران" in dis for dis in disadvantages ):
            return QualityLevel.POOR

        return QualityLevel.AVERAGE

    @staticmethod
    def _generate_tags( product: Product ) -> list[ str ]:
        """‫تولید برچسب‌های استنتاجی

        ‫بر اساس:
        ‫- category
        ‫- price_range
        ‫- مشخصات فنی
        ‫- user_feedback

        Args:
            product: مدل Product

        Returns:
            لیست برچسب‌ها (یکتا)
        """
        tags = []

        # ‫از category
        tags.append( product.category.value )

        # ‫از price_range
        if product.price_range:
            tags.append( product.price_range.value )

        # ‫از specs - Gaming
        if product.specifications.ram_gb and product.specifications.ram_gb >= 12:
            tags.append( "gaming" )

        # ‫از specs - Photography
        if product.specifications.camera_mp and product.specifications.camera_mp >= 48:
            tags.append( "photography" )

        # ‫از specs - Battery Heavy
        if product.specifications.battery_mah and product.specifications.battery_mah >= 5000:
            tags.append( "battery_heavy" )

        # ‫از specs - Lightweight
        if product.specifications.weight_g and product.specifications.weight_g < 180:
            tags.append( "lightweight" )

        # ‫از user_feedback
        if product.user_feedback:
            for adv in product.user_feedback.advantages:
                if "بازی" in adv or "گیم" in adv:
                    tags.append( "gaming" )
                if "عکاسی" in adv or "دوربین" in adv:
                    tags.append( "photography" )
                if "کیفیت ساخت" in adv or "طراحی" in adv:
                    tags.append( "premium_build" )

        # ‫حذف تکراری‌ها
        return sorted( ( set( tags ) ) )
