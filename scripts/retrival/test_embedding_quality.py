"""ارزیابی کیفیت مدل Embedding (ONNX/FP32) با سناریوهای واقعی فارسی"""
import numpy as np
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.services.embedding_service import EmbeddingService


def cosine_similarity( a: list[ float ], b: list[ float ] ) -> float:
    return float( np.dot( a, b ) )


def run_evaluation() -> None:
    settings = get_settings()
    log_message( LG.RETRIEVAL, f"🧪 شروع ارزیابی Embedding | ONNX: {settings.USE_ONNX}", LogLevel.INFO )

    embedder = EmbeddingService()
    tests = {
        "🔹 هم‌راستایی معنایی": [
            ( "گوشی با عمر باتری بالا", "باتری 5000 میلی‌آمپر ساعت با شارژدهی طولانی" ),
            ( "دوربین حرفه‌ای برای عکاسی شب", "سنسور 48 مگاپیکسلی با قابلیت Night Mode" ),
        ],
        "🔸 تمایز محصولات مشابه": [
            ( "آیفون 13 پرو مکس", "آیفون 14 پرو مکس" ),
            ( "گوشی گیمینگ ارزون", "رم 12 گیگ، پردازنده اسنپدراگون، قیمت مناسب" ),
        ],
    }

    all_scores: list[ float ] = []
    for category, pairs in tests.items():
        log_message( LG.RETRIEVAL, f"\n📊 بررسی: {category}", LogLevel.INFO )
        for q, doc in pairs:
            q_vec = embedder.encode( f"query: {q}", is_query=True )[ 0 ]
            d_vec = embedder.encode( f"passage: {doc}", is_query=False )[ 0 ]
            score = cosine_similarity( q_vec, d_vec )
            all_scores.append( score )
            status = "✅ PASS" if score > 0.75 else "⚠️ LOW"
            log_message( LG.RETRIEVAL, f"  {status} | sim={score:.3f} | Q: '{q[:40]}...'", LogLevel.DEBUG )

    mean_score = np.mean( all_scores )
    acceptable = mean_score > 0.75
    log_message( LG.RETRIEVAL, f"\n🎯 میانگین شباهت: {mean_score:.3f} | وضعیت: {'✅ آماده' if acceptable else '❌ نیاز به بررسی'}",
                 LogLevel.INFO )


if __name__ == "__main__":
    run_evaluation()
