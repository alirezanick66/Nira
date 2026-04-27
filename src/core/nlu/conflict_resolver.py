"""‫تشخیص و حل تضاد در فیلترهای استخراج‌شده توسط NLU

‫سناریوهای متناقض رایج:
- «گوشی ارزون ولی پرچم‌دار» (price_range = budget و flagship هم‌زمان)
- «دوربین خوب ولی ارزان» (camera_quality=excellent + price_range=budget) → معمولاً قابل حل
- «رم ۱۶ گیگ زیر ۵ میلیون» (ناسازگاری منطقی)

‫استراتژی حل تضاد (KISS):
1. price > brand > specs (در صورت تضاد، اولویت با قیمت)
2. اگر دو مقدار هم‌سطح برای یک کلید بود (budget vs flagship)، حذف هر دو + هشدار
3. در سایر موارد، آخرین مقدار (last-write-wins) برای استخراج‌های هم‌خانواده

‫خروجی برای فیچر «مدیریت تضاد فیلترها» در ROADMAP فاز MVP Refinement.
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from src.config.logging_config import log_message, LogLevel, LG


@dataclass
class ConflictReport:
    """‫گزارش تضادهای یافت‌شده در فیلترها"""
    conflicts: list[ str ] = field( default_factory=list )
    removed_keys: list[ str ] = field( default_factory=list )
    warnings: list[ str ] = field( default_factory=list )

    @property
    def has_conflicts( self ) -> bool:
        return bool( self.conflicts )

    def summary( self ) -> str:
        if not self.has_conflicts: return "بدون تضاد"
        return f"تضاد‌ها: {', '.join(self.conflicts)} | حذف: {self.removed_keys}"


class ConflictResolver:
    """‫تشخیص‌گر و حل‌کننده تضادهای فیلتر"""

    # ‫گروه‌های متضاد: اگر دو کلمه از یک گروه آمده باشد، تضاد است
    # ‫نکته: متن ورودی توسط PersianNormalizer نرمال شده است، یعنی نیم‌فاصله
    # ‫به فاصله معمولی تبدیل می‌شود. برای همین فرم‌های «پرچم دار» و «پرچم‌دار» هر دو پوشش داده شده‌اند.
    _MUTUALLY_EXCLUSIVE_TERMS: list[ tuple[ str, ... ] ] = [
        # ‫قیمت پایین
        ( "ارزان", "ارزون", "ارزون تر", "ارزان تر", "ارزون‌تر", "ارزان‌تر", "اقتصادی", "بودجه" ),
        # ‫قیمت بالا
        ( "گران", "گرون", "پرچم دار", "پرچم‌دار", "پرچمدار", "لوکس", "premium" ),
    ]

    # ‫مقادیر متضاد در یک کلید (اگر هم‌زمان درخواست شده باشد، تضاد)
    _CONFLICTING_VALUES: dict[ str, list[ tuple[ str, str ] ] ] = {
        "price_range": [
            ( "budget", "flagship" ),
            ( "budget", "premium" ),
        ],
        "battery_quality": [
            ( "poor", "excellent" ),
            ( "poor", "good" ),
        ],
        "camera_quality": [
            ( "poor", "excellent" ),
            ( "poor", "good" ),
        ],
    }

    # ‫اولویت کلیدها در صورت ناسازگاری منطقی (price > brand > specs > qualitative)
    PRIORITY_ORDER: tuple[ str, ... ] = (
        "price",
        "brand",
        "ram_gb",
        "storage_gb",
        "category",
        "price_range",
        "camera_quality",
        "battery_quality",
        "value_for_money",
        "tags",
    )

    @classmethod
    def detect_in_text( cls, text: str ) -> list[ str ]:
        """‫بررسی متن خام کاربر برای کلمات هم‌زمان متضاد

        ‫مثال: «ارزون ولی پرچم‌دار» → ['budget_flagship_conflict']
        """
        conflicts: list[ str ] = []
        present_groups: list[ int ] = []

        for idx, group in enumerate( cls._MUTUALLY_EXCLUSIVE_TERMS ):
            if any( term in text for term in group ):
                present_groups.append( idx )

        # ‫اگر هر دو گروه قیمتی (ارزان + گران) هم‌زمان حاضر باشند → تضاد
        if 0 in present_groups and 1 in present_groups:
            conflicts.append( "price_budget_vs_flagship" )

        return conflicts

    @classmethod
    def resolve( cls, filters: dict[ str, Any ], original_text: str = "" ) -> tuple[ dict[ str, Any ], ConflictReport ]:
        """‫حل تضاد فیلترها بر اساس قوانین اولویت‌بندی

        Args:
            filters: دیکشنری فیلترها (خروجی NLU)
            original_text: متن اصلی کاربر (برای تشخیص دقیق‌تر)

        Returns:
            (فیلترهای پاک‌شده, گزارش تضادها)
        """
        report = ConflictReport()
        cleaned: dict[ str, Any ] = dict( filters )

        # ───── مرحله 1: تضاد در متن ─────
        text_conflicts = cls.detect_in_text( original_text )
        report.conflicts.extend( text_conflicts )

        if "price_budget_vs_flagship" in text_conflicts:
            # ‫حذف price_range متناقض
            if "price_range" in cleaned:
                report.removed_keys.append( "price_range" )
                report.warnings.append( "حذف price_range به‌خاطر تضاد «ارزان ولی پرچم‌دار»" )
                cleaned.pop( "price_range", None )

        # ───── مرحله 2: تضاد در مقدار یک کلید ─────
        # ‫اگر برای یک کلید هم‌زمان دو مقدار متضاد باشد (مثلاً [budget, flagship] در لیست)
        for key, conflict_pairs in cls._CONFLICTING_VALUES.items():
            val = cleaned.get( key )
            if isinstance( val, list ) and len( val ) > 1:
                for a, b in conflict_pairs:
                    if a in val and b in val:
                        report.conflicts.append( f"{key}:{a}_vs_{b}" )
                        report.removed_keys.append( key )
                        cleaned.pop( key, None )
                        break

        # ───── مرحله 3: ناسازگاری منطقی بین قیمت و رم/کیفیت ─────
        # ‫مثال: «رم 16 گیگ زیر 5 میلیون» (در عمل ممکن نیست)
        # ‫در این مرحله فقط هشدار می‌دهیم و فیلتر را حذف نمی‌کنیم
        # ‫چون ممکن است محصول واقعاً وجود داشته باشد و Smart Fallback آن را ریلکس کند.
        price = cleaned.get( "price" )
        ram = cleaned.get( "ram_gb" )
        if isinstance( price, dict ) and isinstance( ram, int ):
            max_price = price.get( "<" ) or price.get( "<=" )
            if max_price and isinstance( max_price, int ):
                # ‫اگر سقف قیمت < 5M و رم >= 12 → ناسازگاری احتمالی
                if max_price < 5_000_000 and ram >= 12:
                    report.warnings.append( f"ناسازگاری احتمالی: رم {ram}GB با سقف قیمت {max_price:,}" )

        if report.has_conflicts:
            log_message(
                LG.NLU,
                f"⚠️ تضاد در فیلترها تشخیص داده شد | {report.summary()}",
                LogLevel.WARNING,
            )

        return cleaned, report
