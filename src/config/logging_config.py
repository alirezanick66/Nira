import sys
from enum import Enum
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from loguru import logger

# ‫پیدا کردن مسیر ریشه پروژه (این فایل در src/config/ قرار دارد)
CURRENT_DIR = Path( __file__ ).resolve().parent.parent.parent
LOG_DIR = CURRENT_DIR / "data" / "logs"
LOG_DIR.mkdir( parents=True, exist_ok=True )


class LG( str, Enum ):
    API = "API"
    DATABASE = "Database"
    DATA_PROCESSING = "DataProcessing"
    RETRIEVAL = "Retrieval"
    LLM = "LLM"
    NLU = "NLU"


class LogLevel( str, Enum ):
    """‫سطح‌های لاگ‌گذاری"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ‫فرمت لاگ کنسول
CONSOLE_FORMAT = ( "<green>{time:YYYY-MM-DD HH:mm}</green> | "
                   "<cyan>{extra[category]}</cyan> | "
                   "<level>{level: <8}</level> | "
                   "<level>{message}</level>{extra[custom_extra]}" )

# ‫فرمت لاگ فایل
FILE_FORMAT = ( "{time:YYYY-MM-DD HH:mm} | {extra[category]} | {level} | {message}{extra[custom_extra]}" )

logger.remove()          # ‫پاک کردن تنظیمات پیش‌فرض loguru

# ‫تنظیم رنگ‌بندی سطح‌ها
logger.level( "INFO", color="<white>" )
logger.level( "DEBUG", color="<light-green>" )
logger.level( "WARNING", color="<yellow>" )
logger.level( "ERROR", color="<red>" )
logger.level( "CRITICAL", color="<red><bold>" )

# ‫لاگ کنسول
logger.add(
    sys.stderr,
    format=CONSOLE_FORMAT,
    colorize=True,
    level="DEBUG",
    filter=lambda record: record[ "extra" ].get( "target" ) == "console",
)

# ‫لاگ فایل — یه فایل جداگانه برای هر دسته
for category in LG:
    logger.add(
        LOG_DIR / f"{category.value.lower()}.log",
        format=FILE_FORMAT,
        level="DEBUG",
        rotation="10 MB",          # چرخش وقتی به 10 مگابایت برسه
        retention=7,          # نگه داشتن 7 فایل بک‌آپ
        encoding="utf-8",
        filter=lambda record, cat=category.value:
        ( record[ "extra" ].get( "category" ) == cat and record[ "extra" ].get( "target" ) == "file" ),
    )


def log_message(
    category: LG,
    message: str,
    level: LogLevel = LogLevel.INFO,
    **kwargs: object,
) -> None:
    """‫ثبت لاگ با پشتیبانی از متن فارسی

    ‫پارامترها:
        category: دسته‌بندی لاگ (از enum LG)
        message: متن پیام
        level: سطح لاگ (پیش‌فرض INFO)
        **kwargs: اطلاعات اضافی برای ضمیمه شدن به لاگ
    """
    # ‫پردازش فارسی فقط برای کنسول — برای فایل خام ذخیره می‌شود
    console_message = get_display( arabic_reshaper.reshape( message ) )
    extra = {
        "category": category.value,
        "custom_extra": f" | {kwargs}" if kwargs else "",
    }

    logger.bind( target="console", **extra ).log( level.value, console_message )
    logger.bind( target="file", **extra ).log( level.value, message )
