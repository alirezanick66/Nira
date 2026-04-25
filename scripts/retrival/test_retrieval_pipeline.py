"""تست یکپارچهٔ بازیابی ترکیبی + رتبه‌بندی نهایی (منطبق با ONNX)"""
import asyncio
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService


async def main() -> None:
    settings = get_settings()
    log_message( LG.RETRIEVAL, f"🧪 شروع تست Retrieval + Rerank | ONNX: {settings.USE_ONNX}", LogLevel.INFO )

    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    query = "گوشی سبک با دوربین عالی برای عکاسی شب و قیمت مناسب"
    log_message( LG.RETRIEVAL, f"🔍 کوئری: {query}", LogLevel.INFO )

    #‫ اجرای متد سنکرون در ThreadPool برای جلوگیری از مسدودسازی event loop
    candidates = await asyncio.to_thread( retriever.search, query=query, top_k=10 )
    log_message( LG.RETRIEVAL, f"✅ {len(candidates)} کاندیدا بازیابی شد", LogLevel.INFO )

    if not candidates:
        log_message( LG.RETRIEVAL, "⚠️ هیچ کاندیدایی یافت نشد", LogLevel.WARNING )
        return

    ranked = await asyncio.to_thread( reranker.rerank, query, candidates, top_k=3 )

    log_message( LG.RETRIEVAL, "📊 نتایج نهایی پس از Reranking:", LogLevel.INFO )
    for i, p in enumerate( ranked, 1 ):
        log_message( LG.RETRIEVAL, f"  {i}. {p.title} | 💰{p.price:,} | 📷{p.camera_quality} | 🏷️{p.price_range}", LogLevel.INFO )


if __name__ == "__main__":
    asyncio.run( main() )
