"""‫تبدیل اعداد نوشتاری فارسی به فرم عددی لاتین‫"""
import re
from src.config.logging_config import log_message, LogLevel, LG


class PersianNumberConverter:
    """‫مبدل سبک و سریع اعداد حروفی فارسی به صحیح‫"""

    _UNITS: dict[ str, int ] = {
        "صفر": 0,
        "یک": 1,
        "یه": 1,
        "دو": 2,
        "سه": 3,
        "چهار": 4,
        "پنج": 5,
        "شش": 6,
        "هفت": 7,
        "هشت": 8,
        "نه": 9,
    }
    _TEENS: dict[ str, int ] = {
        "ده": 10,
        "یازده": 11,
        "دوازده": 12,
        "سیزده": 13,
        "چهارده": 14,
        "پانزده": 15,
        "شانزده": 16,
        "هفده": 17,
        "هجده": 18,
        "نوزده": 19,
    }
    _TENS: dict[ str, int ] = {
        "بیست": 20,
        "سی": 30,
        "چهل": 40,
        "پنجاه": 50,
        "شصت": 60,
        "هفتاد": 70,
        "هشتاد": 80,
        "نود": 90,
    }
    _HUNDREDS: dict[ str, int ] = {
        "صد": 100,
        "یکصد": 100,
        "دویست": 200,
        "سیصد": 300,
        "چهارصد": 400,
        "پانصد": 500,
        "ششصد": 600,
        "هفتصد": 700,
        "هشتصد": 800,
        "نهصد": 900,
    }
    _SCALES: dict[ str, int ] = {
        "هزار": 1_000,
        "میلیون": 1_000_000,
        "میلیارد": 1_000_000_000,
    }
    _CONNECTORS: frozenset[ str ] = frozenset( { "و", "و‌", "و‌‌" } )
    _NOISE_PATTERN: re.Pattern[ str ] = re.compile( r"[‌\- ]+" )

    @classmethod
    def convert( cls, text: str ) -> int | None:
        """‫تبدیل عبارت عددی فارسی به مقدار صحیح‫"""
        cleaned = cls._NOISE_PATTERN.sub( " ", text.strip() ).lower()
        if not cleaned:
            return None

        tokens = [ t for t in cleaned.split() if t not in cls._CONNECTORS ]
        if not tokens:
            return None

        total, current = 0, 0
        lexicon = { **cls._UNITS, **cls._TEENS, **cls._TENS, **cls._HUNDREDS, **cls._SCALES }

        for token in tokens:
            value = lexicon.get( token )
            if value is None:
                return None          #‫توکن نامعتبر → لغو تبدیل

            if value >= 1_000:
                current = max( current, 1 )
                total += current * value
                current = 0
            else:
                current += value

        result = total + current
        log_message( LG.NLU, f"تبدیل عدد حروفی: {text!r} → {result}", LogLevel.DEBUG )
        return result
