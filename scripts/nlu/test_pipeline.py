"""‫اسکریپت تست خط لولهٔ پردازش (Transform + Enrich) روی 20 محصول اول"""
import asyncio
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.engine import DatabaseEngine
from src.data.repositories.product_repository import ProductRepository
from src.data.processing.product_pipeline import ProductProcessingPipeline


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "🧪 شروع تست خط لوله روی 20 محصول اول...", LogLevel.INFO )

    db = DatabaseEngine()
    repo = ProductRepository( db )
    pipeline = ProductProcessingPipeline( repo )
    target_id = 20127115
    product = await pipeline.process( target_id )
    if product:
        log_message( LG.DATA_PROCESSING, f"✅ عنوان: {product.title}", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"💰 قیمت نهایی: {product.price:,} تومان", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"📊 رنج قیمتی: {product.price_range}", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"🔋 کیفیت باتری: {product.battery_quality}", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"📷 کیفیت دوربین: {product.camera_quality}", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"💎 ارزش خرید: {product.value_for_money}", LogLevel.INFO )
        log_message( LG.DATA_PROCESSING, f"🏷️ تگ‌های تولیدشده: {product.tags}", LogLevel.INFO )
    else:
        log_message( LG.DATA_PROCESSING, f"❌ محصول {target_id} پردازش نشد (بررسی کنید در product_raw_cache موجود باشد)",
                     LogLevel.WARNING )

    # ✅ دریافت ۲۰ ID اول از دیتابیس
    # test_ids = await repo.list_raw_product_ids( limit=20 )

    # log_message( LG.DATA_PROCESSING, f"📋 {len(test_ids)} محصول برای تست انتخاب شد", LogLevel.INFO )

    # success_count = 0
    # for idx, pid in enumerate( test_ids, 1 ):
    #     product = await pipeline.process( pid )
    #     if product:
    #         success_count += 1
    #         log_message( LG.DATA_PROCESSING,
    #                      f"✅ [{idx}/{len(test_ids)}] {product.title} | 💰{product.price_range} | 🏷️{len(product.tags)} tags",
    #                      LogLevel.INFO )
    #     else:
    #         log_message( LG.DATA_PROCESSING, f"❌ [{idx}/{len(test_ids)}] پردازش {pid} ناموفق بود", LogLevel.WARNING )

    # log_message( LG.DATA_PROCESSING, f"🎯 پایان تست | موفق: {success_count}/{len(test_ids)} ({100*success_count//len(test_ids)}%)",
    #              LogLevel.INFO )


if __name__ == "__main__":
    asyncio.run( main() )
