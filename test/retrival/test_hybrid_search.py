"""‫تست جستجوی ترکیبی با Qdrant"""
import asyncio
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.config.logging_config import log_message, LogLevel, LG
from src.config.domain_loader import DomainConfigLoader


async def main() -> None:
    log_message( LG.RETRIEVAL, "🧪 شروع تست Hybrid Search + RRF...", LogLevel.INFO )
    domain_config = DomainConfigLoader()
    retriever = QdrantHybridRetriever( domain_config=domain_config.load( "mobile" ) )

    # ‫تست ۱: کوئری ساده بدون فیلتر
    results = retriever.search(
        query=" Galaxy S25 Ultra",
        top_k=5,
    )
    log_message( LG.RETRIEVAL, f"📋 نتایج کوئری ساده: {len(results)} محصول", LogLevel.INFO )
    for i, p in enumerate( results, 1 ):
        log_message(
            LG.RETRIEVAL,
            f" title :  {p.title}\nid: {p.product_id}\nprice: {p.price}\nprice_range: {p.price_range}\ncamera_summary: {p.camera_summary}\ncamera_quality: {p.camera_quality}\n..................",
            LogLevel.DEBUG,
        )

    # # ‫تست ۲: کوئری با فیلتر قیمت و برند
    # results_filtered = retriever.search(
    #     query="آیفون ارزان",
    #     filters={
    #         "price": {
    #             "<": 200000000
    #         },
    #         "brand": "اپل"
    #     },
    #     top_k=3,
    # )
    # log_message( LG.RETRIEVAL, f"📋 نتایج فیلترشده: {len(results_filtered)} محصول", LogLevel.INFO )
    # for i, p in enumerate( results_filtered, 1 ):
    #     log_message( LG.RETRIEVAL, f"  {i}. {p.title} | 💰{p.price:,}", LogLevel.DEBUG )


if __name__ == "__main__":
    asyncio.run( main() )
