import asyncio
from src.data.db.engine import DatabaseEngine
from src.data.repositories.product_repository import ProductRepository
from src.data.processing.product_pipeline import ProductProcessingPipeline


async def main() -> None:
    db = DatabaseEngine()
    repo = ProductRepository( db )
    pipeline = ProductProcessingPipeline( repo )

    # تست روی یکی از IDهای ذخیره‌شده
    product = await pipeline.process( product_id=20481188 )
    if product:
        print( f"✅ محصول غنی‌شده: {product.title}" )
        print( f"🏷️ Price Range: {product.price_range}" )
        print( f"🔋 Battery: {product.battery_quality} | 📷 Camera: {product.camera_quality}" )
    else:
        print( "❌ پردازش ناموفق بود." )


if __name__ == "__main__":
    asyncio.run( main() )
