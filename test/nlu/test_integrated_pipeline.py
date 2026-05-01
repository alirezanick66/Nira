"""اسکریپت تست یکپارچه کل پایپلاین: NLU → Hybrid Retrieval → Reranker"""

#───────────────────── Imports ─────────────────────
import asyncio

#───────────────────── Local Imports ─────────────────────
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.config.logging_config import log_message, LogLevel, LG
from src.config.settings import get_settings
from src.config.domain_loader import DomainConfigLoader


async def main() -> None:
    settings = get_settings()
    log_message( LG.RETRIEVAL, f"🧪 شروع تست یکپارچه پایپلاین | ONNX: {settings.USE_ONNX}", LogLevel.INFO )

    domain_config = DomainConfigLoader()
    nlu = NLUPipeline()
    retriever = QdrantHybridRetriever( domain_config=domain_config.load( "mobile" ) )
    reranker = RerankerService()

    test_queries = [
        'یه گوشی   آیفون میخوام که   برای عکاسی عالی باشه',
          # "گوشی گیمینگ با رم بالا زیر 30 میلیون تومان",
          # "بین آیفون و سامسونگ کدوم بهتره؟",
          # "یه چیز گرونتر ولی با باتری قویتر نشون بده",
          # "گوشی با دوربین خوب که ارزش خرید بالایی داشته باشه",
          # "یه موبایل گیمینگ خوب به جز برند شیائومی",
    ]

    for query in test_queries:
        log_message( LG.RETRIEVAL, f"\n🚀 کوئری: '{query}'", LogLevel.INFO )

        # 🔹 گام ۱: درک زبان طبیعی (NLU)
        nlu_out = nlu.process( query )
        log_message( LG.RETRIEVAL, f"   🔹 Intent: {nlu_out.intent} | Filters: {nlu_out.metadata_filters}", LogLevel.DEBUG )

        if nlu_out.is_greeting:
            log_message( LG.RETRIEVAL, "   🤝 پاسخ سیستمی: سلام! چطور می‌تونم در انتخاب محصول کمکتون کنم؟", LogLevel.INFO )
            continue

        if nlu_out.intent == "refine":
            log_message( LG.RETRIEVAL, "   🔄 Intent: refine → نیاز به Conversation Memory (فاز بعدی)", LogLevel.INFO )

        # 🔹 گام ۲: بازیابی ترکیبی (اجرای غیرمسدودکننده در ThreadPool)
        candidates = await asyncio.to_thread( retriever.search,
                                              query=nlu_out.semantic_query,
                                              filters=nlu_out.metadata_filters,
                                              top_k=10 )
        log_message( LG.RETRIEVAL, f"   🔍 بازیابی: {len(candidates)} کاندیدا از Qdrant", LogLevel.DEBUG )

        if not candidates:
            log_message( LG.RETRIEVAL, "   ⚠️ محصولی با فیلترهای درخواستی یافت نشد", LogLevel.WARNING )
            continue

        # 🔹 گام ۳: مرتب‌سازی نهایی (اجرای غیرمسدودکننده)
        final_results = await asyncio.to_thread( reranker.rerank, query=query, payloads=candidates, top_k=3 )

        log_message( LG.RETRIEVAL, "   🎯 نتایج نهایی پس از Rerank:", LogLevel.INFO )
        for i, p in enumerate( final_results, 1 ):
            log_message( LG.RETRIEVAL, f"      {i}. {p.title[:65]}... | 💰 {p.price:,} | 📷 {p.camera_quality} | 🏷️ {p.price_range}",
                         LogLevel.INFO )
        log_message( LG.RETRIEVAL, "-" * 70, LogLevel.DEBUG )


if __name__ == "__main__":
    asyncio.run( main() )
