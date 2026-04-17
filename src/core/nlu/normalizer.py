import re
from src.config.logging_config import log_message, LogLevel, LG


class PersianNormalizer:
    """
    نرمال‌سازی پیشرفته متن فارسی
   ‫ شامل fix کردن باگ‌های Hazm و بهینه‌سازی با str.translate
    """
    _CHAR_MAP = {
          # ‫حروف عربی به فارسی
        'ي': 'ی',
        'ك': 'ک',
        'ى': 'ی',
        'ہ': 'ه',
        'ۀ': 'ه',
        'ة': 'ه',
          # ‫اعداد عربی به فارسی
        '٠': '۰',
        '١': '۱',
        '٢': '۲',
        '٣': '۳',
        '٤': '۴',
        '٥': '۵',
        '٦': '۶',
        '٧': '۷',
        '٨': '۸',
        '٩': '۹',
    }

    # ‫ساخت جدول ترجمه برای استفاده در متد translate
    _TRANS_TABLE = str.maketrans( _CHAR_MAP )

    def __init__( self ):
        log_message( LG.DATA_PROCESSING, f"Custom Persian Normalizer آماده شد ", LogLevel.INFO )

    def _fix_chars_and_numbers( self, text: str ) -> str:
        """ ‫تبدیل یکپارچه حروف و اعداد با استفاده از translate (بسیار سریع)"""
        return text.translate( self._TRANS_TABLE )

    def _fix_zwnj( self, text: str ) -> str:
        """‫اصلاح نیم‌فاصله — تبدیل به فاصله معمولی"""
        # ‫چند نیم‌فاصله پشت سر هم → یکی
        text = re.sub( r'‌+', ' ', text )
        # ‫نیم‌فاصله احاطه‌شده با فاصله → یک فاصله
        text = re.sub( r' *‌ *', ' ', text )
        return text

    def _remove_diacritics( self, text: str ) -> str:
        """حذف اعراب"""
        return re.sub( r'[ًٌٍَُِّْ]', '', text )

    def _remove_kashida( self, text: str ) -> str:
        """حذف کشیده"""
        return text.replace( 'ـ', '' )

    def _fix_number_punctuation( self, text: str ) -> str:
        """اصلاح علائم در اعداد"""

        # اعشار: 0 ٫ 5 -> 0.5
        text = re.sub( r'([\d۰-۹])\s*٫\s*([\d۰-۹])', r'\1.\2', text )

        # هزارگان: حذف فاصله و تبدیل کاما
        # ابتدا کاما فارسی → کاما انگلیسی
        text = re.sub( r'(?<=\d)\s*،\s*(?=\d{3}(?:\D|$))', ',', text )

        # حذف فاصله اضافی کنار کاما
        text = re.sub( r'(?<=\d)\s*,\s*(?=\d)', ',', text )

        # درصد: 60 ٪ -> 60%
        text = re.sub( r'(\d)\s+[٪%]', r'\1%', text )

        return text

    def _fix_spacing_and_punctuation( self, text: str ) -> str:
        """
        ادغام شده: حذف فاصله‌های اضافی و اصلاح فاصله علائم نگارشی
        ترتیب اجرا بسیار مهم است تا نتیجه نهایی صحیح باشد.
        """

        # ‫1. اضافه کردن فاصله بعد از علائم (اگر جا افتاده باشد)
        # نکته: ما فقط بعد از علائم فاصله اضافه می‌کنیم.
        text = re.sub( r'([.،؛!?])(?=\S)', r'\1 ', text )

        # ‫2. اصلاح فاصله بعد از دو نقطه (با احتیاط برای لینک‌ها)
        # ‫اگر قبلش اسلش یا عدد نبود (برای جلوگیری از خراب کردن http:// یا ساعت 12:30)
        text = re.sub( r'(?<![:/])(?<!\d):(?!\d)', r': ', text )

        # ‫3. حذف فاصله قبل از علائم نگارشی (بسته شدن پرانتز، کاما، نقطه و ...)
        # این کار باید بعد از مرحله 1 انجام شود تا تداخل نداشته باشد
        punctuations_no_space_before = r'([.,;:!?،؛ـ\)\]}"\'»«])'
        text = re.sub( rf'\s+{punctuations_no_space_before}', r'\1', text )

        # ‫4. حذف فاصله بعد از علائم باز (پرانتز باز، گیومه باز)
        text = re.sub( r'([(\["\'«])\s+', r'\1', text )

        # ‫5. تبدیل چند فاصله پشت سر هم به یک فاصله (General Cleanup)
        # این کار باید در انتها انجام شود تا نتیجه مراحل بالا تمیز شود
        text = re.sub( r'[^\S\n]+', ' ', text )

        # ‫6. حذف فاصله‌های ابتدا و انتها
        text = text.strip()

        return text

    def normalize( self, text: str, remove_diacritics: bool = True, remove_kashida: bool = True ) -> str:
        """
        نرمال‌سازی کامل متن فارسی
        """
        try:
            if not text or not isinstance( text, str ):
                return ""

            # ‫2. تبدیل حروف عربی و اعداد (جایگزین حلقه‌های کند)
            text = self._fix_chars_and_numbers( text )

            # ‫3. اصلاح نیم‌فاصله
            text = self._fix_zwnj( text )

            # ‫4. حذف اعراب
            if remove_diacritics:
                text = self._remove_diacritics( text )

            # ‫5. حذف کشیده
            if remove_kashida:
                text = self._remove_kashida( text )

            # ‫6. اصلاح علائم در اعداد
            text = self._fix_number_punctuation( text )

            # 7. اضافه کردن فاصله بعد از علائم نگارشی
            text = self._fix_spacing_and_punctuation( text )

            return text

        except Exception as e:
            log_message( LG.DATA_PROCESSING, f"خطا در نرمال‌سازی متن: {str(e)}", LogLevel.WARNING )
            # بازگشت حداقلی متن تمیز شده در صورت خطا
            return " ".join( text.split() )


# Instance سراسری
persian_normalizer = PersianNormalizer()
