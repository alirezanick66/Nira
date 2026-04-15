"""‫سرویس سینکرون اکسپورت داده‌های خام API به JSON برای تحلیل
‫این ماژول صرفاً برای دیباگ و آنالیز دستی داده‌های خام پیش از پردازش نهایی طراحی شده است.
"""
#───────────────────── Imports ─────────────────────
import json
from pathlib import Path

#───────────────────── Local Imports ─────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class JsonAnalysisExporter:
    """‫صادرکنندهٔ داده‌های خام به فرمت JSON جهت تحلیل و دیباگ"""

    def __init__( self ) -> None:
        self._settings = get_settings()
        self._file_path = Path( self._settings.TEST_LIST_IDS_OUTPUT )
        self._file_path.parent.mkdir( parents=True, exist_ok=True )

    #───────────────────── Private Methods ─────────────────────

    def _load( self ) -> list[ dict[ str, object ] ]:
        """‫بارگذاری لیست محصولات از فایل JSON موجود"""
        if not self._file_path.exists():
            return []
        try:
            with open( self._file_path, "r", encoding="utf-8" ) as fh:
                return json.load( fh )
        except ( json.JSONDecodeError, OSError ) as exc:
            log_message( LG.DATA_PROCESSING, f"خطا در بارگذاری فایل تحلیل: {exc}", LogLevel.WARNING )
            return []

    def _update_or_append( self, data_list: list[ dict[ str, object ] ], product_id: int, raw_data: dict[ str, object ] ) -> None:
        """‫جایگزینی رکورد تکراری یا افزودن رکورد جدید بر اساس product_id"""

        # ‫بررسی وجود product_id در ساختار تودرتوی پاسخ API
        for idx, item in enumerate( data_list ):
            data = item.get( "data" )
            if isinstance( data, dict ):
                product = data.get( "product" )
                if isinstance( product, dict ):
                    if product.get( "id" ) == product_id:
                        data_list[ idx ] = raw_data
                        return
        data_list.append( raw_data )

    def _save( self, data_list: list[ dict[ str, object ] ] ) -> None:
        """‫ذخیره نهایی لیست در فایل JSON با فرمت خوانا"""
        try:
            with open( self._file_path, "w", encoding="utf-8" ) as fh:
                json.dump( data_list, fh, ensure_ascii=False, indent=4 )
            log_message( LG.DATA_PROCESSING, f"فایل تحلیل به‌روزرسانی شد | {len(data_list)} رکورد", LogLevel.DEBUG )
        except OSError as exc:
            log_message( LG.DATA_PROCESSING, f"خطا در ذخیره فایل تحلیل: {exc}", LogLevel.ERROR )
            raise

    #───────────────────── Public Methods ─────────────────────

    def append( self, product_id: int, raw_data: dict[ str, object ] ) -> Path:
        """‫الحاق یا به‌روزرسانی داده خام در فایل JSON تحلیلی

        Args:
            product_id: شناسه محصول
            raw_data: دیکشنری خام پاسخ API

        Returns:
            مسیر فایل خروجی
        """
        data_list = self._load()
        self._update_or_append( data_list, product_id, raw_data )
        self._save( data_list )
        return self._file_path
