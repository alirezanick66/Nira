"""‫اسکریپت تست ایندکس‌سازی محصولات در Qdrant"""
#───────────────────── Imports ─────────────────────
import asyncio

#───────────────────── Local Imports ─────────────────────
from src.data.db.engine import DatabaseEngine
from src.data.repositories.product_repository import ProductRepository
from src.data.processing.product_pipeline import ProductProcessingPipeline
from src.core.vector.qdrant_indexer import QdrantIndexer
from src.config.logging_config import log_message, LogLevel, LG
from src.config.settings import get_settings


async def main() -> None:
    log_message( LG.DATA_PROCESSING, "🧪 شروع تست ایندکس‌سازی Qdrant...", LogLevel.INFO )

    db = DatabaseEngine()
    repo = ProductRepository( db )
    pipeline = ProductProcessingPipeline( repo )
    indexer = QdrantIndexer()

    # # پردازش ۱۰ محصول نمونه از دیتابیس
    # test_product = await pipeline.process( 20127115 )
    test_ids = await repo.list_raw_product_ids()
    products = []
    for pid in test_ids:
        prod = await pipeline.process( pid )
        if prod:
            products.append( prod )

    if not products:
        log_message( LG.DATA_PROCESSING, "هیچ محصولی برای ایندکس‌سازی یافت نشد", LogLevel.WARNING )
        return

    products = [ p for p in products if p.price > 0 ]
    # آپلود به Qdrant
    count = indexer.index_products( products, vector_size=get_settings().EMBEDDING_DIM )
    log_message( LG.DATA_PROCESSING, f"✅ پایان تست | {count} محصول آماده جستجوی ترکیبی", LogLevel.INFO )


if __name__ == "__main__":
    asyncio.run( main() )
