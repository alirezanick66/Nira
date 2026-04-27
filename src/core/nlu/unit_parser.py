"""‫پارسر هوشمند اعداد، واحدها و عبارات قیمتی فارسی محاوره‌ای

‫این ماژول مسئول استخراج دقیق:
- اعداد فارسی به حروف («سی میلیون» → 30,000,000)
- اعداد عددی محاوره‌ای («30تومن»، «۲۵ت») 
- بازه‌ها («حدود ۴۰-۵۰ میلیون»)
- واحدهای حافظه/رم با تفکیک GB/MB/TB
- اعداد مدل‌های گوشی («آیفون ۱۵»، «S24») که نباید به‌عنوان مقدار قیمت/رم استخراج شوند

‫خروجی برای فیچر «پارسینگ پیشرفته اعداد/واحد» در ROADMAP فاز MVP Refinement.
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import re
from dataclasses import dataclass


@dataclass( frozen=True )
class PriceFilter:
    """‫نتیجه استخراج فیلتر قیمت"""
    min_value: int | None = None
    max_value: int | None = None

    def to_dict( self ) -> dict[ str, int ]:
        """‫تبدیل به فرمت سازگار با QdrantHybridRetriever (Range)"""
        out: dict[ str, int ] = {}
        if self.min_value is not None: out[ ">=" ] = self.min_value
        if self.max_value is not None: out[ "<" ] = self.max_value
        return out

    @property
    def is_empty( self ) -> bool:
        return self.min_value is None and self.max_value is None


@dataclass( frozen=True )
class UnitValue:
    """‫مقدار عددی همراه با واحد استانداردشده"""
    value: int
    unit: str          # GB, MB, TB, mAh, ...


class UnitParser:
    """‫پارسر هوشمند برای اعداد، واحدها و عبارات قیمت فارسی

    ‫نکات کلیدی طراحی:
    - ابتدا اعداد فارسی-حرفی (سی، چهل، …) به دیجیت تبدیل می‌شوند
    - سپس بازه‌ها (`30 تا 50 میلیون`، `۴۰-۵۰`) تشخیص داده می‌شود
    - عددهای مدل (`آیفون 15`، `S24`، `Note 13`) از قیمت/رم جدا می‌شوند
    - واحدهای حافظه با اولویت TB > GB > MB استخراج می‌شوند
    """

    # ─────────── 1) اعداد حرفی فارسی ───────────
    _WORD_NUMBERS: dict[ str, int ] = {
          # دهگان
        "ده": 10,
        "بیست": 20,
        "سی": 30,
        "چهل": 40,
        "پنجاه": 50,
        "شصت": 60,
        "هفتاد": 70,
        "هشتاد": 80,
        "نود": 90,
          # یکان (برای ترکیب با میلیون/میلیارد)
        "یک": 1,
        "دو": 2,
        "سه": 3,
        "چهار": 4,
        "پنج": 5,
        "شش": 6,
        "هفت": 7,
        "هشت": 8,
        "نه": 9,
          # ‫ترکیب‌های پرکاربرد (به‌جای پارسر کامل برای سادگی KISS)
        "صد": 100,
        "دویست": 200,
        "سیصد": 300,
        "چهارصد": 400,
        "پانصد": 500,
        "ششصد": 600,
        "هفتصد": 700,
        "هشتصد": 800,
        "نهصد": 900,
    }

    # ‫کلمات بین یکان و دهگان
    _CONNECTOR = "و"

    # ─────────── 2) واحدها ───────────
    _PRICE_UNITS: dict[ str, int ] = {
        "میلیارد": 1_000_000_000,
        "میلیون": 1_000_000,
        "هزار": 1_000,
    }

    _CURRENCY_TOKENS: tuple[ str, ...] = ( "تومان", "تومن", "ت" )

    # ─────────── 3) Regex Patterns ───────────
    # عدد قابل پارس (دیجیت یا اعشار)
    _NUM = r"\d+(?:[\.,]\d+)?"

    # ‫نشانگرهای ابهام
    _APPROX = r"(?:حدود|تقریبا|تقریباً|نزدیک)"

    # ─────────── 4) Stop words & Model number indicators ───────────
    # ‫کلماتی که قبل از یک عدد بیایند، آن عدد به عنوان «شماره مدل» شناخته می‌شود نه قیمت/رم
    _MODEL_PREFIX_KEYWORDS: tuple[ str, ...] = (
        "آیفون",
        "iphone",
        "گلکسی",
        "galaxy",
        "نوت",
        "note",
        "اس",
        "s",
        "a",
        "redmi",
        "ردمی",
        "پوکو",
        "poco",
        "میت",
        "mate",
        "p",
        "pixel",
        "پیکسل",
        "ai",
        "pro",
        "max",
        "ultra",
        "plus",
        "lite",
        "se",
    )

    # ‫الگوی شناسایی شماره مدل (مثلاً S24, Note13, A52, iPhone 15)
    # ‫کلمه + عدد یا حرف+عدد چسبیده
    _MODEL_INLINE = re.compile( r"\b([A-Za-z]+)\s*\d+\b" )

    @classmethod
    def parse_word_number( cls, text: str ) -> int | None:
        """‫تبدیل عدد حرفی فارسی به دیجیت
        
        ‫مثال‌ها:
        - "سی"            → 30
        - "چهل و پنج"     → 45
        - "صد و بیست"     → 120
        - "دویست و پنجاه" → 250

        Returns:
            None اگر هیچ عددی پیدا نشد.
        """
        text = text.strip()
        if not text: return None

        tokens = text.split()
        total = 0
        found = False

        for tok in tokens:
            if tok in cls._WORD_NUMBERS:
                total += cls._WORD_NUMBERS[ tok ]
                found = True
            elif tok == cls._CONNECTOR:
                continue
            else:
                # ‫توکن غیرعددی → پایان
                break

        return total if found else None

    @classmethod
    def _replace_word_numbers_with_digits( cls, text: str ) -> str:
        """‫پیش‌پردازش: «سی میلیون» → «30 میلیون»

        ‫به‌جای پارسر کامل، با اولویت‌بندی الگوهای ساده ولی پرکاربرد
        ‫از خراب کردن متن جلوگیری می‌کند.
        """
        # ‫الگوی «<عدد حرفی> [و <یکان>] <واحد>»
        # ‫مثلاً «چهل و پنج میلیون» یا «صد میلیون»
        words_sorted = sorted( cls._WORD_NUMBERS.keys(), key=len, reverse=True )

        # ‫الگوی پیچیده: ترکیب دهگان + و + یکان (مثلاً "چهل و پنج")
        compound_pattern = re.compile( rf"\b(?P<base>{'|'.join(words_sorted)})(?:\s+و\s+(?P<add>{'|'.join(words_sorted)}))?\b" )

        def repl( m: re.Match[ str ] ) -> str:
            base = cls._WORD_NUMBERS[ m.group( "base" ) ]
            add_word = m.group( "add" )
            add = cls._WORD_NUMBERS[ add_word ] if add_word else 0
            return str( base + add )

        return compound_pattern.sub( repl, text )

    @classmethod
    def _mask_model_numbers( cls, text: str ) -> tuple[ str, list[ str ] ]:
        """‫جایگزینی موقت اعداد مدل با placeholder تا با قیمت/رم اشتباه نشوند

        ‫مثال‌ها (مسک می‌شوند):
        - "آیفون ۱۵"  → "آیفون __MODEL_0__"
        - "S24"        → "__MODEL_0__"
        - "گلکسی نوت 13" → "گلکسی نوت __MODEL_0__"

        Returns:
            (متن مسک‌شده, لیست مقادیر اصلی برای بازگشت)
        """
        masked = text
        masks: list[ str ] = []

        # ‫الگوی 1: کلمه‌کلیدی مدل + عدد جداگانه
        keywords_pattern = "|".join( re.escape( kw ) for kw in cls._MODEL_PREFIX_KEYWORDS )
        kw_num_pattern = re.compile( rf"\b({keywords_pattern})\s+(\d+)\b", re.IGNORECASE )

        def repl_kw( m: re.Match[ str ] ) -> str:
            masks.append( m.group( 2 ) )
            return f"{m.group(1)} __MODEL_{len(masks)-1}__"

        masked = kw_num_pattern.sub( repl_kw, masked )

        # ‫الگوی 2: حرف‌+عدد چسبیده مثل S24 / A52 / Note13
        inline_pattern = re.compile( r"\b([A-Za-z]{1,5})(\d+)\b" )

        def repl_inline( m: re.Match[ str ] ) -> str:
            masks.append( m.group( 2 ) )
            return f"{m.group(1)}__MODEL_{len(masks)-1}__"

        masked = inline_pattern.sub( repl_inline, masked )

        return masked, masks

    # ────────────────────────────────────────────────
    #                 پارسرهای اصلی
    # ────────────────────────────────────────────────

    @classmethod
    def extract_price_filter( cls, text: str ) -> PriceFilter:
        """‫استخراج فیلتر قیمت از متن فارسی محاوره‌ای

        ‫پشتیبانی از:
        - "زیر 30 میلیون"             → max=30M
        - "بالای ۲۰ میلیون"           → min=20M
        - "حدود سی میلیون"            → 25M..35M (±15%)
        - "بین 30 تا 50 میلیون"       → 30M..50M
        - "30تومن" / "۳۰ت"            → max=30 * 1.5 (تخمین)
        - "40-50 میلیون"              → 40M..50M
        """
        # ‫مرحله 1: نرمال‌سازی - مسک کردن اعداد مدل
        masked_text, _ = cls._mask_model_numbers( text )

        # ‫مرحله 2: تبدیل اعداد حرفی به دیجیت
        digit_text = cls._replace_word_numbers_with_digits( masked_text )

        # ‫الگوی بازه: «<عدد> [<واحد>] (تا|الی|-) <عدد> [<واحد>] [تومان]»
        unit_alt = "|".join( cls._PRICE_UNITS.keys() )
        currency_alt = "|".join( cls._CURRENCY_TOKENS )

        range_pattern = re.compile(
            rf"({cls._NUM})\s*({unit_alt})?\s*(?:تا|الی|-)\s*({cls._NUM})\s*({unit_alt})?\s*"
            rf"(?:{currency_alt})?", re.IGNORECASE )

        if m := range_pattern.search( digit_text ):
            low = cls._to_toman( m.group( 1 ), m.group( 2 ) or m.group( 4 ) )
            high = cls._to_toman( m.group( 3 ), m.group( 4 ) or m.group( 2 ) )
            if low is not None and high is not None:
                return PriceFilter( min_value=min( low, high ), max_value=max( low, high ) )

        # ‫الگوی تک‌مقداری با اپراتور
        operator_pattern = re.compile(
            rf"(?P<op>زیر|بالای|کمتر(?:\s+از)?|بیشتر(?:\s+از)?|حداکثر|حداقل|تا|از)?\s*"
            rf"(?P<approx>{cls._APPROX})?\s*"
            rf"(?P<num>{cls._NUM})\s*"
            rf"(?P<unit>{unit_alt})?\s*"
            rf"(?P<curr>{currency_alt})?",
            re.IGNORECASE,
        )

        for m in operator_pattern.finditer( digit_text ):
            op = ( m.group( "op" ) or "" ).strip()
            approx = bool( m.group( "approx" ) )
            unit = m.group( "unit" ) or ""
            curr = m.group( "curr" ) or ""

            # ‫باید یا واحد قیمتی (میلیون/میلیارد/هزار) باشد یا توکن ارز
            has_unit = bool( unit )
            has_currency = bool( curr )
            has_op = bool( op )

            if not ( has_unit or has_currency or has_op ):
                continue          # ‫عدد بدون نشانه قیمت → احتمالاً مربوط به قیمت نیست

            value = cls._to_toman( m.group( "num" ), unit, currency=curr )
            if value is None: continue

            if approx:
                # ‫بازه ±15٪
                margin = int( value * 0.15 )
                return PriceFilter( min_value=value - margin, max_value=value + margin )

            if op in { "زیر", "کمتر", "کمتر از", "حداکثر", "تا" }:
                return PriceFilter( max_value=value )
            if op in { "بالای", "بیشتر", "بیشتر از", "حداقل", "از" }:
                return PriceFilter( min_value=value )

            # ‫بدون اپراتور ولی با واحد → سقف تخمینی
            return PriceFilter( max_value=int( value * 1.5 ) )

        return PriceFilter()

    @classmethod
    def extract_memory_filter( cls, text: str, key: str = "ram" ) -> UnitValue | None:
        """‫استخراج رم/حافظه با تفکیک واحد (GB/MB/TB)

        Args:
            text: متن خام
            key: 'ram' یا 'storage'

        Returns:
            UnitValue با value و unit نرمال‌شده، یا None
        """
        # ‫مسک کردن اعداد مدل
        masked, _ = cls._mask_model_numbers( text )

        # ‫کلمات کلیدی برای هر نوع
        if key == "ram":
            keyword_alt = r"رم|ram"
        else:          # storage
            keyword_alt = r"حافظ[هه]\s*داخلی|حافظ[هه]|storage|حافظه"

        # ‫الگو: «<عدد> <واحد> رم» یا «رم <عدد> <واحد>»
        unit_alt = r"(?P<unit>گیگ\s*(?:ابایت|ا)?|gb|gig|تر[اا]?بایت|tb|مگ\s*(?:ابایت)?|mb)"
        num = cls._NUM

        patterns = [
            re.compile( rf"({num})\s*{unit_alt}\s*(?:{keyword_alt})", re.IGNORECASE ),
            re.compile( rf"(?:{keyword_alt})\s*({num})\s*{unit_alt}", re.IGNORECASE ),
            re.compile( rf"(?:{keyword_alt})\s*({num})\s*", re.IGNORECASE ),          # بدون واحد صریح
        ]

        for pat in patterns:
            if m := pat.search( masked ):
                raw_num = float( m.group( 1 ).replace( ",", "." ) )
                unit_raw = ( m.groupdict().get( "unit" ) or "" ).lower()
                unit = cls._normalize_memory_unit( unit_raw )

                # ‫اگر واحد صریح نبود، از روی مقدار حدس بزن
                if unit is None:
                    if key == "ram":
                        unit = "GB"          # رم همیشه GB
                    else:
                        unit = "TB" if raw_num >= 1 and raw_num <= 4 and "tb" in masked.lower() else "GB"

                return UnitValue( value=int( raw_num ), unit=unit )

        return None

    @classmethod
    def extract_battery_filter( cls, text: str ) -> UnitValue | None:
        """‫استخراج ظرفیت باتری (mAh)"""
        masked, _ = cls._mask_model_numbers( text )
        # ‫الگو: «<عدد> میلی آمپر» یا «<عدد> mah» یا «باتری <عدد>»
        pattern = re.compile( rf"({cls._NUM})\s*(?:میلی\s*آمپر(?:\s*ساعت)?|mah)", re.IGNORECASE )
        if m := pattern.search( masked ):
            val = int( float( m.group( 1 ).replace( ",", "." ) ) )
            return UnitValue( value=val, unit="mAh" )

        # ‫الگوی نسبی: «باتری بزرگ» / «باتری قوی» → خیلی محتاطانه (در qualitative_mappings است)
        return None

    # ────────────────────────────────────────────────
    #                  ابزارهای کمکی
    # ────────────────────────────────────────────────

    @staticmethod
    def _normalize_memory_unit( unit: str ) -> str | None:
        """‫تبدیل واحد خام به فرم استاندارد: GB/MB/TB"""
        if not unit: return None
        u = unit.lower().strip()
        if u.startswith( ( "گیگ", "gb", "gig" ) ): return "GB"
        if u.startswith( ( "مگ", "mb" ) ): return "MB"
        if u.startswith( ( "تر", "tb" ) ): return "TB"
        return None

    @classmethod
    def _to_toman( cls, num_str: str, unit: str | None, currency: str = "" ) -> int | None:
        """‫تبدیل عدد + واحد به مقدار تومانی نهایی"""
        try:
            base = float( num_str.replace( ",", "." ) )
        except ValueError:
            return None

        if unit:
            mult = cls._PRICE_UNITS.get( unit, 1 )
            return int( base * mult )

        # ‫بدون واحد ولی با ارز («30 تومن»):
        # ‫احتمال زیاد منظور «30 میلیون تومن» است (محاوره ایرانی)
        if currency and base < 1000:
            return int( base * 1_000_000 )

        return int( base ) if base >= 1000 else None
