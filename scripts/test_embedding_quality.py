"""‫اسکریپت ارزیابی کیفیت مدل Embedding برای جستجوی محصول فارسی
‫معیارها:
1. هم‌راستایی معنایی (Semantic Alignment)
2. تمایز محصولات مشابه (Differentiation)
3. مقاومت در برابر زبان محاوره‌ای و ترکیبی (Robustness)
4. توزیع امتیازات شباهت کسینوسی (Score Distribution)
"""
import numpy as np
from src.services.embedding_service import EmbeddingService
from src.config.logging_config import log_message, LogLevel, LG


def cosine_similarity( a: list[ float ], b: list[ float ] ) -> float:
    """‫محاسبهٔ شباهت کسینوسی بین دو بردار نرمال‌شده"""
    return float( np.dot( a, b ) )


async def run_evaluation() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع ارزیابی مدل Embedding...", LogLevel.INFO )
    embedder = EmbeddingService.get_instance()

    # ==================== سناریوهای تست ====================
    tests = {
        "🔹 هم‌راستایی معنایی": [
            ( "گوشی با عمر باتری بالا", "باتری 5000 میلی‌آمپر ساعت با شارژدهی طولانی" ),
            ( "دوربین حرفه‌ای برای عکاسی شب", "سنسور 48 مگاپیکسلی با قابلیت Night Mode" ),
            ( "گوشی سبک و خوش‌دست", "وزن 165 گرم، طراحی ارگونومیک" ),
        ],
        "🔸 تمایز محصولات مشابه": [
            ( "آیفون 13 پرو مکس", "آیفون 14 پرو مکس" ),
            ( "سامسونگ گلکسی A54", "سامسونگ گلکسی A55" ),
            ( "شیائومی Redmi Note 12", "پوکو X5 پرو" ),
        ],
        "🔹 زبان محاوره‌ای و ترکیبی": [
            ( "گوشی گیمینگ ارزون", "رم 12 گیگ، پردازنده اسنپدراگون، قیمت مناسب" ),
            ( "یه گوشی میخوام که خیلی سریع شارژ بشه", "شارژ سریع 120 وات، پر شدن کامل در 20 دقیقه" ),
            ( "iphone se 2022 vs samsung s21", "آیفون SE نسل سوم در مقابل سامسونگ گلکسی S21" ),
        ],
    }

    results: dict[ str, list[ tuple[ str, str, float, str ] ] ] = {}
    all_scores: list[ float ] = []

    for category, pairs in tests.items():
        log_message( LG.RETRIEVAL, f"\n📊 بررسی: {category}", LogLevel.INFO )
        category_results = []

        for q, doc in pairs:
            # E5 نیاز به پیشوند دارد. سرویس قبلاً آن را اعمال می‌کند، اما برای اطمینان صریح:
            q_vec = embedder.encode( f"query: {q}", is_query=True )[ 0 ]
            d_vec = embedder.encode( f"passage: {doc}", is_query=False )[ 0 ]

            score = cosine_similarity( q_vec, d_vec )
            all_scores.append( score )

            status = "✅ PASS" if ( score > 0.75 or ( category.startswith( "🔸" ) and score < 0.65 ) ) else "⚠️ LOW"
            category_results.append( ( q, doc, score, status ) )
            log_message( LG.RETRIEVAL, f"  {status} | sim={score:.3f} | Q: '{q[:40]}...'", LogLevel.DEBUG )

        results[ category ] = category_results

    # ==================== تحلیل آماری ====================
    mean_score = np.mean( all_scores )
    std_score = np.std( all_scores )
    log_message( LG.RETRIEVAL, f"\n📈 آمار کلی:", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"  میانگین شباهت: {mean_score:.3f}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"  انحراف معیار: {std_score:.3f}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"  حداقل: {min(all_scores):.3f} | حداکثر: {max(all_scores):.3f}", LogLevel.INFO )

    # ==================== معیار پذیرش نهایی ====================
    acceptable = (
        mean_score > 0.75 and min( all_scores ) > 0.70          # اطمینان از عدم افت شدید در کوئری‌های محاوره‌ای
    )
    log_message( LG.RETRIEVAL,
                 f"\n🎯 وضعیت نهایی: {'✅ مدل برای Production آماده است' if acceptable else '❌ نیاز به بررسی/تنظیم آستانه دارد'}",
                 LogLevel.INFO )


if __name__ == "__main__":
    import asyncio
    asyncio.run( run_evaluation() )
