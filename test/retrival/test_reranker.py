""" تست ایزوله سرویس Reranker برای بررسی رفتار روی کوئری مقایسه """
import asyncio
from src.config.settings import get_settings
from src.services.reranker_service import RerankerService
from src.core.vector.qdrant_payload import QdrantProductPayload


async def main():
    settings = get_settings()
    reranker = RerankerService( settings )

    # شبیه‌سازی ۴ کاندیدا (شامل آیفون ۱۶ و ۱۷)
    mock_payloads = [
        QdrantProductPayload( product_id=20127115,
                              is_available=True,
                              rating=4.8,
                              rating_count=1200,
                              title="گوشی موبایل اپل مدل iPhone 17 CH دو سیم کارت",
                              price=284999000,
                              category="موبایل",
                              brand="اپل",
                              price_range="premium",
                              ram_gb=8,
                              storage_gb=256,
                              search_text="آیفون ۱۷" ),
        QdrantProductPayload(
            product_id=17986495,
            is_available=True,
            rating=4.7,
            rating_count=1100,
            title="گوشی موبایل اپل مدل iPhone 16 CH دو سیم کارت",          # محصول مورد نظر تو
            price=239999000,
            category="موبایل",
            brand="اپل",
            price_range="premium",
            ram_gb=8,
            storage_gb=128,
            search_text="آیفون ۱۶" ),
        QdrantProductPayload( product_id=20125788,
                              is_available=True,
                              rating=4.9,
                              rating_count=1300,
                              title="گوشی موبایل اپل مدل iPhone 17 Pro Max ZA",
                              price=531999000,
                              category="موبایل",
                              brand="اپل",
                              price_range="flagship",
                              ram_gb=12,
                              storage_gb=512,
                              search_text="آیفون ۱۷ پرو مکس" ),
        QdrantProductPayload( product_id=99999999,
                              title="گوشی موبایل سامسونگ مدل Galaxy S24",
                              price=250000000,
                              category="موبایل",
                              brand="سامسونگ",
                              price_range="premium",
                              ram_gb=8,
                              storage_gb=256,
                              search_text="گلکسی اس ۲۴",
                              is_available=True,
                              rating=4.6,
                              rating_count=1000 )
    ]

    query = "بین iPhone 16 و iPhone 17 کدومشون بهتره"

    print( f"\n🔍 در حال رتبه‌بندی {len(mock_payloads)} محصول برای کوئری: '{query}'\n" )

    # دریافت امتیازهای خام برای شفافیت کامل
    scored_results = reranker.rerank_with_scores( query, mock_payloads )

    for rank, ( payload, score ) in enumerate( scored_results, 1 ):
        print( f"رتبه {rank} | امتیاز: {score:.4f} | ID: {payload.product_id} | {payload.title}" )

    print( "\n✅ خروجی نهایی متد rerank (Top-4):" )
    final_reranked = reranker.rerank( query, mock_payloads, top_k=4 )
    for p in final_reranked:
        print( f"-> ID: {p.product_id} | {p.title}" )


if __name__ == "__main__":
    asyncio.run( main() )
