"""‫تست جستجوی ترکیبی با Qdrant"""
import asyncio
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.config.logging_config import log_message, LogLevel, LG


async def main() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع تست Hybrid Search + RRF...", LogLevel.INFO )

    retriever = QdrantHybridRetriever()

    # ‫تست ۱: کوئری ساده بدون فیلتر
    results = retriever.search(
        query="گوشی سبک با دوربین خوب",
        dense_vector=None,          # 🟡 Placeholder
        top_k=5,
    )
    log_message( LG.RETRIEVAL, f"📋 نتایج کوئری ساده: {len(results)} محصول", LogLevel.INFO )
    for i, p in enumerate( results, 1 ):
        log_message( LG.RETRIEVAL, f"  {i}. {p.title} | 💰{p.price:,} | 🏷️{p.tags}", LogLevel.DEBUG )

    # ‫تست ۲: کوئری با فیلتر قیمت و برند
    results_filtered = retriever.search(
        query="آیفون ارزان",
        dense_vector=None,
        filters={
            "price": {
                "<": 50_000_000
            },
            "brand": "اپل"
        },
        top_k=3,
    )
    log_message( LG.RETRIEVAL, f"📋 نتایج فیلترشده: {len(results_filtered)} محصول", LogLevel.INFO )
    for i, p in enumerate( results_filtered, 1 ):
        log_message( LG.RETRIEVAL, f"  {i}. {p.title} | 💰{p.price:,}", LogLevel.DEBUG )


if __name__ == "__main__":
    asyncio.run( main() )
