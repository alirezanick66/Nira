"""‫ابزارهای نرمال‌سازی مشخصات فنی

‫این ماژول برای استخراج و تبدیل مشخصات فنی از متن فارسی طراحی شده
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
import re
from typing import Any


class SpecNormalizer:
    """‫نرمال‌ساز مشخصات فنی"""

    # ‫نگاشت واحدها به انگلیسی
    UNIT_MAP = {
        "گیگابایت": "GB",
        "گیگ": "GB",
        "مگابایت": "MB",
        "مگ": "MB",
        "میلی آمپر ساعت": "mAh",
        "میلی‌آمپر": "mAh",
        "اینچ": "inch",
        "مگاپیکسل": "MP",
        "گرم": "g",
        "کیلوگرم": "kg",
        "هرتز": "Hz",
        "گیگاهرتز": "GHz",
    }
    _UNIT_SCALE: dict[ str, float ] = {
        "مگابایت": 1 / 1024,
        "مگ": 1 / 1024,
        "mb": 1 / 1024,
        "گیگابایت": 1.0,
        "گیگ": 1.0,
        "gb": 1.0,
        "ترابایت": 1024.0,
        "tb": 1024.0,
        "میلی آمپر": 1.0,
        "میلی‌آمپر": 1.0,
        "mah": 1.0,
    }
    #────────────────────────────────────────── Public Methods ──────────────────────────────────────────
    @classmethod
    def extract_specifications( cls, raw_specs: list[ dict ] ) -> dict[ str, Any ]:
        """‫استخراج و نرمال‌سازی کامل مشخصات فنی

        Args:
            raw_specs: لیست specifications خام از API دیجی‌کالا

        Returns:
            dict شامل فیلدهای نرمال شده:
                - ram_gb
                - storage_gb
                - battery_mah
                - screen_size_inch
                - camera_mp
                - weight_g
                - os
                - processor
                - release_year

        Example:
            >>> raw = [{"attributes": [{"title": "مقدار RAM", "values": ["8 گیگابایت"]}]}]
            >>> extract_specifications(raw)
            {"ram_gb": 8, ...}
        """
        specs = {
            "raw_specifications": raw_specs,
            "ram_gb": None,
            "storage_gb": None,
            "battery_mah": None,
            "screen_size_inch": None,
            "camera_mp": None,
            "weight_g": None,
            "os": None,
            "processor": None,
            "release_year": None,
        }

        for category in raw_specs:
            for attr in category.get( "attributes", [] ):
                title = attr.get( "title", "" ).lower()
                values = attr.get( "values", [] )

                if not values:
                    continue

                value_text = values[ 0 ]          # ‫اولین مقدار

                # ‫RAM
                if "ram" in title or "رم" in title:
                    specs[ "ram_gb" ] = cls._parse_to_base_unit( value_text )

                # ‫Storage
                elif "حافظه داخلی" in title or "storage" in title:
                    specs[ "storage_gb" ] = cls._parse_to_base_unit( value_text )

                # ‫Battery
                elif "باتری" in title or "battery" in title:
                    specs[ "battery_mah" ] = cls._parse_to_base_unit( value_text, default_unit="mah" )

                # ‫Screen Size
                elif "اندازه" in title or "سایز" in title or "صفحه" in title:
                    if "اینچ" in value_text or "inch" in value_text.lower():
                        specs[ "screen_size_inch" ] = cls._extract_float( value_text )

                # ‫Camera
                elif "دوربین" in title or "camera" in title:
                    if "مگاپیکسل" in value_text or "mp" in value_text.lower():
                        specs[ "camera_mp" ] = cls._extract_number( value_text )

                # ‫Weight
                elif "وزن" in title or "weight" in title:
                    specs[ "weight_g" ] = cls._extract_number( value_text )

                # ‫OS
                elif "سیستم عامل" in title or "operating system" in title:
                    # ‫تشخیص نوع OS
                    value_lower = value_text.lower()
                    if "ios" in value_lower:
                        specs[ "os" ] = "iOS"
                    elif "android" in value_lower:
                        specs[ "os" ] = "Android"
                    else:
                        specs[ "os" ] = value_text

                # ‫Processor
                elif "تراشه" in title or "پردازنده" in title or "processor" in title or "chipset" in title:
                    specs[ "processor" ] = value_text

                # ‫Release Date/Year
                elif "معرفی" in title or "زمان معرفی" in title or "تاریخ" in title:
                    specs[ "release_year" ] = cls._extract_year( value_text )

        return specs

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    @staticmethod
    def _extract_number( text: str ) -> float | None:
        """‫استخراج اولین عدد از متن

        Examples:
            "256 گیگابایت" → 256
            "4832 میلی آمپر ساعت" → 4832
            "6.9 اینچ" → 6.9 (float)

        Args:
            text: متن ورودی

        Returns:
            عدد استخراج شده یا‫ None
        """
        if not text:
            return None

        # ‫حذف کاما و فاصله
        text = text.replace( ",", "" ).replace( "٬", "" )

        # ‫پیدا کردن اولین عدد
        match = re.search( r"\d+(?:\.\d+)?", text )
        if match:
            try:
                return float( match.group() )
            except ValueError:
                return None

        return None

    @staticmethod
    def _extract_float( text: str ) -> float | None:
        """‫استخراج عدد اعشاری از متن

        Examples:
            "6.9 اینچ" → 6.9
            "۴.۵ میلی آمپر" → 4.5

        Args:
            text: متن ورودی

        Returns:
           ‫ عدد اعشاری یا None
        """
        if not text:
            return None

        # ‫تبدیل اعداد فارسی به انگلیسی
        persian_to_english = str.maketrans( "۰۱۲۳۴۵۶۷۸۹", "0123456789" )
        text = text.translate( persian_to_english )

        # ‫حذف کاما
        text = text.replace( ",", "" ).replace( "٬", "" )

        # ‫پیدا کردن عدد اعشاری
        match = re.search( r"\d+\.?\d*", text )
        if match:
            try:
                return float( match.group() )
            except ValueError:
                return None

        return None

    @classmethod
    def _extract_unit( cls, text: str ) -> str | None:
        """‫استخراج واحد از متن

        Examples:
            "256 گیگابایت" → "GB"
            "4832 میلی آمپر ساعت" → "mAh"

        Args:
            text: متن ورودی

        Returns:
           ‫ واحد استاندارد یا None
        """
        if not text:
            return None

        text_lower = text.lower()
        for persian_unit, english_unit in cls.UNIT_MAP.items():
            if persian_unit in text_lower:
                return english_unit

        return None

    @staticmethod
    def _extract_year( text: str ) -> int | None:
        """‫استخراج سال از متن

        Examples:
            "09 سپتامبر 2025" → 2025
            "معرفی شده در 2024" → 2024

        Args:
            text: متن ورودی

        Returns:
            سال (4 رقمی) یا None
        """
        if not text:
            return None

        # ‫پیدا کردن عدد 4 رقمی که با 20 شروع بشه
        match = re.search( r"20\d{2}", text )
        if match:
            year = int( match.group() )
            # ‫اعتبارسنجی ساده (بین 2000 تا 2030)
            if 2000 <= year <= 2030:
                return year

        return None

    @classmethod
    def _parse_to_base_unit( cls, text: str, default_unit: str = "gb" ) -> float | None:
        """استخراج عدد و تبدیل خودکار به واحد پایه (GB/mAh)"""
        if not text: return None
        clean = text.lower().replace( "٬", "" ).replace( ",", " " )
        # پیدا کردن عدد (صحیح یا اعشاری)
        num_match = re.search( r"(\d+(?:[.,]\d+)?)", clean )
        if not num_match: return None
        raw_val = float( num_match.group( 1 ).replace( ",", "." ) )

        # تشخیص ضریب واحد
        multiplier = 1.0
        for unit, scale in cls._UNIT_SCALE.items():
            if unit in clean:
                multiplier = scale
                break
        return round( raw_val * multiplier, 4 )
