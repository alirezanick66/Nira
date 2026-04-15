"""‫اسکریپت تست استخراج شناسه محصولات از API دیجی‌کالا"""

# ───────────────────── Imports ─────────────────────
import asyncio
import json
from pathlib import Path
import traceback

#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.data.fetchers.digikala_api import DigikalaAPIClient
from src.config.settings import get_settings


async def collect_product_ids( max_products: int | None = None ) -> list[ int ]:
    """‫جمع‌آوری شناسه محصولات تا حد مشخص

    Args:
        max_products: حداکثر تعداد شناسه برای جمع‌آوری

    Returns:
        لیست شناسه‌های عددی
    """
    ids: list[ int ] = []
    async with DigikalaAPIClient() as client:
        # ‫برای تست، فقط صفحه اول پیمایش می‌شود
        async for pid in client.stream_product_ids():
            ids.append( pid )
            if max_products is not None and len( ids ) >= max_products:
                break
    return ids


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "شروع تست استخراج شناسه محصولات...", LogLevel.INFO )
    try:
        ids = await collect_product_ids()

        output_path = Path( get_settings().TEST_LIST_IDS_OUTPUT )
        output_path.parent.mkdir( parents=True, exist_ok=True )

        with open( output_path, "w", encoding="utf-8" ) as fh:
            json.dump( ids, fh, ensure_ascii=False, indent=4 )

        log_message( LG.DATA_PROCESSING, f"✅ {len(ids)} شناسه استخراج و در {output_path} ذخیره شد", LogLevel.INFO )
    except Exception as exc:
        log_message( LG.DATA_PROCESSING, f"❌ خطای غیرمنتظره در تست: {type(exc).__name__}", LogLevel.ERROR )
        log_message( LG.DATA_PROCESSING, f"Traceback:\n{traceback.format_exc()}", LogLevel.ERROR )


if __name__ == "__main__":
    asyncio.run( main() )
