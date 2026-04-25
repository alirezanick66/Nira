"""‫اسکریپت تست یکپارچه کل پایپلاین: NLU → Hybrid Retrieval → Reranker"""
#───────────────────── imports ─────────────────────
import asyncio

#───────────────────── local imports ─────────────────────
from src.core.nlu.nlu_pipeline import nlu_pipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.config.logging_config import log_message, LogLevel, LG


async def main() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع تست یکپارچه کل پایپلاین...", LogLevel.INFO )

    # بارگذاری سرویس‌ها (یک‌بار، با الگوی Singleton)
    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    test_queries = [
        "یه گوشی سبک و ارزون برای عکاسی میخوام", "گوشی گیمینگ با رم بالا زیر 30 میلیون تومان", "بین آیفون و سامسونگ کدوم بهتره؟",
        "یه چیز گرونتر ولی با باتری قویتر نشون بده"
    ]

    for query in test_queries:
        log_message( LG.RETRIEVAL, f"\n🚀 کوئری: '{query}'", LogLevel.INFO )

        # 🔹 گام ۱: درک زبان طبیعی (NLU)
        nlu_out = nlu_pipeline.process( query )
        log_message( LG.RETRIEVAL, f"   🔹 Intent: {nlu_out.intent} | Filters: {nlu_out.metadata_filters}", LogLevel.DEBUG )

        if nlu_out.is_greeting:
            log_message( LG.RETRIEVAL, "   🤝 پاسخ سیستمی: سلام! چطور می‌تونم در انتخاب محصول کمکتون کنم؟", LogLevel.INFO )
            continue

        if nlu_out.intent == "compare":
            log_message( LG.RETRIEVAL, "   🔄 Intent: compare → نیاز به LLM Comparison Engine (فاز بعدی)", LogLevel.INFO )
            log_message( LG.RETRIEVAL, "   📦 کاندیداهای بازیابی‌شده برای مقایسه:", LogLevel.DEBUG )
            for i, p in enumerate( candidates[ :2 ], 1 ):
                log_message( LG.RETRIEVAL, f"      {i}. {p.title[:60]}...", LogLevel.DEBUG )
            continue

        if nlu_out.intent == "refine":
            log_message( LG.RETRIEVAL, "   🔄 Intent: refine → نیاز به Conversation Memory (فاز بعدی)", LogLevel.INFO )
            log_message( LG.RETRIEVAL, f"   🔍 فعلاً با فیلتر مطلق پردازش شد: {nlu_out.metadata_filters}", LogLevel.DEBUG )

        # 🔹 گام ۲: بازیابی ترکیبی (Dense + Sparse + RRF + Metadata Filter)
        candidates = retriever.search(
            query=nlu_out.semantic_query,
            filters=nlu_out.metadata_filters,
            top_k=10          # دریافت ۱۰ کاندیدا برای رتبه‌بندی دقیق‌تر
        )
        log_message( LG.RETRIEVAL, f"   🔍 بازیابی: {len(candidates)} کاندیدا از Qdrant", LogLevel.DEBUG )

        if not candidates:
            log_message( LG.RETRIEVAL, "   ⚠️ محصولی با فیلترهای درخواستی یافت نشد", LogLevel.WARNING )
            continue

        # 🔹 گام ۳: مرتب‌سازی نهایی (Cross-Encoder Reranker)
        final_results = reranker.rerank(
            query=query,          # استفاده از متن کامل برای درک بهتر Context
            payloads=candidates,
            top_k=3 )

        log_message( LG.RETRIEVAL, f"   🎯 نتایج نهایی پس از Rerank:", LogLevel.INFO )
        for i, p in enumerate( final_results, 1 ):
            log_message( LG.RETRIEVAL, f"      {i}. {p.title[:65]}... | 💰 {p.price:,} | 📷 {p.camera_quality} | 🏷️ {p.price_range}",
                         LogLevel.INFO )
        log_message( LG.RETRIEVAL, "-" * 70, LogLevel.DEBUG )


if __name__ == "__main__":
    asyncio.run( main() )
