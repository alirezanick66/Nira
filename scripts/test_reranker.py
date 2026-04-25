"""‫اسکریپت تست یکپارچه: Hybrid Retrieval → Reranker"""
import asyncio
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService
from src.config.logging_config import log_message, LogLevel, LG


async def main() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع تست یکپارچه Retrieval + Rerank...", LogLevel.INFO )

    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    query = "گوشی سبک با دوربین عالی برای عکاسی شب و قیمت مناسب"
    log_message( LG.RETRIEVAL, f"🔍 کوئری: {query}", LogLevel.INFO )

    # ۱. بازیابی ۲۰ کاندیدا از Qdrant
    candidates = retriever.search( query=query, top_k=20 )
    log_message( LG.RETRIEVAL, f"✅ {len(candidates)} کاندیدا از Hybrid Search بازیابی شد", LogLevel.INFO )

    if not candidates:
        log_message( LG.RETRIEVAL, "⚠️ هیچ کاندیدایی یافت نشد", LogLevel.WARNING )
        return

    # ۲. رتبه‌بندی دقیق با Reranker
    ranked = reranker.rerank( query, candidates, top_k=3 )

    log_message( LG.RETRIEVAL, "📊 نتایج نهایی پس از Reranking:", LogLevel.INFO )
    for i, p in enumerate( ranked, 1 ):
        log_message( LG.RETRIEVAL, f"  {i}. {p.title} | 💰{p.price:,} | 📷{p.camera_quality} | 🏷️{p.price_range}", LogLevel.INFO )


if __name__ == "__main__":
    asyncio.run( main() )
