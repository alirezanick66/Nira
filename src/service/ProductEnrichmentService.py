""" تحلیل نیاز های کاربر بر اساس اطلاعات وارد شده"""

#==================== Imports داخلی پروژه ====================
from datetime import datetime

from src.data.models.core.product import PriceRange, QualityLevel


def calculate_price_range( self ) -> PriceRange:
    """ ‫ محاسبه رنج قیمتی بر اساس بودجه کاربر"""
    price_toman = self.price

    if price_toman < 10_000_000:
        return PriceRange.BUDGET
    elif price_toman < 30_000_000:
        return PriceRange.MID
    elif price_toman < 60_000_000:
        return PriceRange.PREMIUM
    else:
        return PriceRange.FLAGSHIP


def _infer_battery_from_specs( self ) -> QualityLevel:
    """‫استنتاج کیفیت باتری از مشخصات فنی"""
    battery = self.specifications.battery_mah
    if not battery:
        return QualityLevel.UNKNOWN

    if battery >= 5000:
        return QualityLevel.EXCELLENT
    elif battery >= 4000:
        return QualityLevel.GOOD
    elif battery >= 3000:
        return QualityLevel.AVERAGE
    else:
        return QualityLevel.POOR


def _infer_camera_from_specs( self ) -> QualityLevel:
    """‫استنتاج کیفیت دوربین از مشخصات فنی"""
    camera = self.specifications.camera_mp
    if not camera:
        return QualityLevel.UNKNOWN

    if camera >= 48:
        return QualityLevel.EXCELLENT
    elif camera >= 12:
        return QualityLevel.GOOD
    else:
        return QualityLevel.AVERAGE


def infer_quality_levels( self ) -> None:
    """‫استنتاج سطح کیفیت از specs و user_feedback

    ‫این متد فیلدهای battery_quality، camera_quality و value_for_money رو پر می‌کنه
    """
    # ‫باتری
    if self.user_feedback:
        if any( "باتری" in adv or "شارژ" in adv for adv in self.user_feedback.advantages ):
            self.battery_quality = QualityLevel.EXCELLENT
        elif any( "باتری" in dis or "شارژ" in dis for dis in self.user_feedback.disadvantages ):
            self.battery_quality = QualityLevel.POOR
        else:
            self.battery_quality = self._infer_battery_from_specs()
    else:
        self.battery_quality = self._infer_battery_from_specs()

    # ‫دوربین
    if self.user_feedback:
        if any( "دوربین" in adv or "عکس" in adv for adv in self.user_feedback.advantages ):
            self.camera_quality = QualityLevel.EXCELLENT
        elif any( "دوربین" in dis or "عکس" in dis for dis in self.user_feedback.disadvantages ):
            self.camera_quality = QualityLevel.POOR
        else:
            self.camera_quality = self._infer_camera_from_specs()
    else:
        self.camera_quality = self._infer_camera_from_specs()

    # ‫ارزش خرید
    if self.user_feedback:
        if any( "قیمت" in adv or "ارزان" in adv for adv in self.user_feedback.advantages ):
            self.value_for_money = QualityLevel.GOOD
        elif any( "قیمت" in dis or "گران" in dis for dis in self.user_feedback.disadvantages ):
            self.value_for_money = QualityLevel.POOR
        else:
            self.value_for_money = QualityLevel.AVERAGE
    else:
        self.value_for_money = QualityLevel.AVERAGE


def generate_tags( self ) -> list[ str ]:
    """‫تولید برچسب‌های استنتاجی

    ‫بر اساس specs و user_feedback، tag های مناسب رو تولید می‌کنه
    """
    tags = []

    # ‫از category
    tags.append( self.category.value )

    # ‫از price_range
    if self.price_range:
        tags.append( self.price_range.value )

    # ‫از specs
    if self.specifications.ram_gb and self.specifications.ram_gb >= 12:
        tags.append( "gaming" )

    if self.specifications.camera_mp and self.specifications.camera_mp >= 48:
        tags.append( "photography" )

    if self.specifications.battery_mah and self.specifications.battery_mah >= 5000:
        tags.append( "battery_heavy" )

    if self.specifications.weight_g and self.specifications.weight_g < 180:
        tags.append( "lightweight" )

    # ‫از user_feedback
    if self.user_feedback:
        for adv in self.user_feedback.advantages:
            if "بازی" in adv or "گیم" in adv:
                tags.append( "gaming" )
            if "عکاسی" in adv or "دوربین" in adv:
                tags.append( "photography" )

    return list( set( tags ) )          # ‫حذف تکراری‌ها


def prepare_for_storage( self ) -> None:
    """‫آماده‌سازی برای ذخیره

        ‫این متد باید قبل از ذخیره در DB فراخوانی بشه
        """
    # ‫محاسبه price_range
    self.price_range = self.calculate_price_range()

    # ‫استنتاج کیفیت‌ها
    self.infer_quality_levels()

    # ‫تولید tags
    self.tags = self.generate_tags()

    # ‫به‌روزرسانی زمان
    self.updated_at = datetime.utcnow()
