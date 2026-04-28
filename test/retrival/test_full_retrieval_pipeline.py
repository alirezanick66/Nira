""" ‫تست تخصصی لایه‌ی Embedding + Reranker (بدون دخالت NLU یا فیلترهای متادیتا)
هدف: سنجش دقت درک معنایی، تمایز ظریف مشخصات، و رتبه‌بندی هوشمند توسط Cross-Encoder
"""
#───────────────────── Imports ─────────────────────
import asyncio
#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService

# ⚠️ کوئری‌های حرفه‌ای طراحی‌شده برای استرس‌تست درک معنایی
TEST_QUERIES = [ {
    "id": 1,
    "query": "گوشی با دوربین عالی برای عکاسی در شب و نور کم",
    "target": "تطابق معنایی با دوربین قوی + قابلیت‌های نور کم/عکاسی شبانه"
}, {
    "id": 2,
    "query": "گوشی روان و سریع برای کارهای روزمره و باز کردن همزمان چند برنامه",
    "target": "تطابق با رم بالا/پردازنده قوی + توضیحات عملکرد روان و مولتی‌تسکینگ"
}, {
    "id": 3,
    "query": "گوشی با صفحه نمایش باکیفیت و اسپیکر بلند برای تماشای فیلم و سریال",
    "target": "تطابق با نمایشگر آمولد/نرخ نوسازی بالا + صدای استریو/تمرکز رسانه‌ای"
}, {
    "id": 5,
    "query": "گوشی میان‌رده با دوربین قابل قبول و طراحی شیک و مدرن",
    "target": "تطابق با رنج قیمتی متوسط + دوربین متوسط/خوب + تمرکز روی طراحی ظاهری و سبک"
} ]


async def test_embedding_reranker() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع تست تخصصی Embedding + Reranker (ایزوله از NLU)", LogLevel.INFO )

    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    for case in TEST_QUERIES:
        log_message( LG.RETRIEVAL, f"\n{'='*70}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"📌 تست #{case['id']} | کوئری: {case['query']}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"🎯 هدف مورد انتظار: {case['target']}", LogLevel.DEBUG )

        # 🔹 مرحله ۱: بازیابی گسترده (فقط معنایی + کلیدواژه، بدون فیلتر متادیتا)
        candidates = await asyncio.to_thread( retriever.search, query=case[ 'query' ], filters=None, top_k=10 )
        log_message( LG.RETRIEVAL, f"⬇️  {len(candidates)} کاندیدا بازیابی شد (قبل از Rerank)", LogLevel.INFO )

        if not candidates:
            log_message( LG.RETRIEVAL, "⚠️ هیچ کاندیدایی یافت نشد. ایندکس خالی یا اتصال قطع است.", LogLevel.WARNING )
            continue

        # لاگ ۵ تای اول قبل از ریرنک
        for i, p in enumerate( candidates[ :5 ], 1 ):
            log_message( LG.RETRIEVAL,
                         f"   {i}. {p.title[:60]}... | 💰{p.price:,} | 🏷️{p.brand} | 📷{p.camera_quality} | 💵{p.value_for_money}",
                         LogLevel.DEBUG )

        # 🔹 مرحله ۲: رتبه‌بندی دقیق با Cross-Encoder
        ranked = await asyncio.to_thread( reranker.rerank, query=case[ 'query' ], payloads=candidates, top_k=3 )

        log_message( LG.RETRIEVAL, "🏆 نتایج نهایی پس از Reranking:", LogLevel.INFO )
        for i, p in enumerate( ranked, 1 ):
            log_message( LG.RETRIEVAL,
                         f"   {i}. {p.title[:70]}... | 💰{p.price:,} | 🏷️{p.brand} | 📷{p.camera_quality} | 💵{p.value_for_money}",
                         LogLevel.INFO )

        log_message( LG.RETRIEVAL, "💡 ارزیابی دستی: آیا رتبهٔ ۱ و ۲ با 'هدف مورد انتظار' همخوانی دارند؟", LogLevel.INFO )
        log_message( LG.RETRIEVAL, "-" * 70, LogLevel.DEBUG )


if __name__ == "__main__":
    asyncio.run( test_embedding_reranker() )
