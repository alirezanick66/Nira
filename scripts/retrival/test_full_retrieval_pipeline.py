""" ‫تست هدفمند Embedding + Reranker روی سناریوهای شکست Embedding"""
import asyncio
from typing import List, Tuple
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.services.reranker_service import RerankerService


# ── مجموعه تست با هدف پوشش ضعف‌های Embedding ──
def get_challenge_queries() -> List[ Tuple[ str, str, str ] ]:
    """
   ‫ برمی‌گرداند: (دسته, کوئری, شرح نتیجهٔ ایده‌آل)
    """
    return [
        ( "منفی‌سازی (غیر آیفون)", " گوشی  با باتری قوی و دوربین خوب اما آیفون نباشه",
          "باید محصولی غیر از اپل در رتبهٔ اول باشد. آیفون‌ها اگر هم آمدند، رتبهٔ پایین بگیرند." ),
        ( "منفی‌سازی (غیر شیائومی)", "یه موبایل گیمینگ خوب به جز برند شیائومی", "برند شیائومی نباید رتبهٔ اول را بگیرد." ),
        ( "تمایز مدل‌های بسیار نزدیک", "گوشی موبایل شیائومی Redmi Note 14 Pro 4G", "مدل دقیق 4G باید بالاتر از 5G قرار گیرد." ),
        ( "تمایز اعداد ظریف (رم)", "گوشی با رم ۱۲ گیگابایت", "محصولات ۱۲ گیگ رم باید بر ۸ گیگ مقدم باشند." ),
        ( "تشخیص مفهوم ضمنی 'قیمت مناسب' (با کمک فیلتر متنی در سند)", "گوشی با دوربین خوب که ارزش خرید بالایی داشته باشه",
          "محصولی با value_for_money خوب (مثلاً 'excellent') در صدر باشد." ),
    ]


async def test_weakness_scenarios() -> None:
    settings = get_settings()
    log_message( LG.RETRIEVAL, "🧪 شروع تست هدفمند Embedding + Reranker روی نقاط ضعف", LogLevel.INFO )

    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    for category, query, ideal_desc in get_challenge_queries():
        log_message( LG.RETRIEVAL, f"\n{'='*60}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"📌 دسته: {category}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"🔍 کوئری: {query}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"💡 انتظار: {ideal_desc}", LogLevel.DEBUG )

        # مرحله ۱: بازیابی اولیه (تنها با HybridSearch، بدون فیلتر اضافه)
        candidates = await asyncio.to_thread( retriever.search, query=query, top_k=5 )
        log_message( LG.RETRIEVAL, f"⬇️  {len(candidates)} کاندیدا (قبل از Reranking):", LogLevel.INFO )
        for i, p in enumerate( candidates[ :5 ], 1 ):
            log_message(
                LG.RETRIEVAL, f"   {i}. {p.title[:80]}... | 💰{p.price:,} | 🏷️{getattr(p,'brand','?')} | "
                f"رم={p.ram_gb} | دوربین={p.camera_quality}", LogLevel.DEBUG )

        # مرحله ۲: Reranking
        ranked = await asyncio.to_thread( reranker.rerank, query, candidates, top_k=3 )

        log_message( LG.RETRIEVAL, f"🏆 نتایج نهایی پس از Reranking:", LogLevel.INFO )
        for i, p in enumerate( ranked, 1 ):
            log_message(
                LG.RETRIEVAL, f"   {i}. {p.title[:90]}... | 💰{p.price:,} | 🏷️{getattr(p,'brand','?')} | "
                f"رم={p.ram_gb} | دوربین={p.camera_quality} | ارزش خرید={p.value_for_money}", LogLevel.INFO )

        # ارزیابی دستی (می‌توان با چک‌های خودکار جایگزین کرد)
        if category == "منفی‌سازی (غیر آیفون)":
            top_brand = getattr( ranked[ 0 ], 'brand', '' )
            if top_brand and 'اپل' not in str( top_brand ).lower():
                log_message( LG.RETRIEVAL, "✅ Reranker موفق به حذف آیفون از رتبهٔ اول شد.", LogLevel.INFO )
            else:
                log_message( LG.RETRIEVAL, "❌ Reranker هنوز آیفون را بالا نشانده است.", LogLevel.WARNING )

        if category == "تمایز مدل‌های بسیار نزدیک":
            # بررسی کند که آیا مدل 4G در رتبهٔ اول است
            first_title = ranked[ 0 ].title.lower() if ranked else ""
            if "4g" in first_title and "5g" not in first_title:
                log_message( LG.RETRIEVAL, "✅ مدل 4G به‌درستی در صدر است.", LogLevel.INFO )
            else:
                log_message( LG.RETRIEVAL, "❌ مدل 4G اول نشد، Reranker تمایز کافی نداشت.", LogLevel.WARNING )


if __name__ == "__main__":
    asyncio.run( test_weakness_scenarios() )
