"""ارزیابی پیشرفتهٔ کیفیت مدل Embedding (ONNX/FP32) با سناریوهای چالشی فارسی"""
import numpy as np
from typing import List, Tuple, Dict
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.services.embedding_service import EmbeddingService


# ── توابع کمکی ─────────────────────────────────
def cosine_similarity( a: List[ float ], b: List[ float ] ) -> float:
    """محاسبهٔ شباهت کسینوسی بین دو بردار نرمال‌شده"""
    return float( np.dot( a, b ) )


def evaluate_retrieval( query_vec: List[ float ], pos_vecs: List[ List[ float ] ], neg_vecs: List[ List[ float ] ] ) -> Dict:
    """
    ارزیابی یک query در برابر مجموعه‌ای از اسناد مثبت و منفی.
    معیارها:
      - precision@1: آیا برترین سند یک نمونهٔ مثبت است؟
      - rank: رتبهٔ اولین سند مثبت (۱‑indexed)
      - reciprocal_rank: ۱/rank
      - mean_sim_pos: میانگین شباهت با اسناد مثبت
      - mean_sim_neg: میانگین شباهت با اسناد منفی
    """
    # ساخت لیست اسناد و برچسب (۱: مثبت، ۰: منفی)
    all_vecs = pos_vecs + neg_vecs
    labels = [ 1 ] * len( pos_vecs ) + [ 0 ] * len( neg_vecs )

    if not all_vecs:
        return { "precision@1": False, "mrr": 0.0, "rank": 0 }

    # محاسبهٔ شباهت‌ها و مرتب‌سازی نزولی
    sims = [ cosine_similarity( query_vec, dv ) for dv in all_vecs ]
    sorted_indices = np.argsort( sims )[ ::-1 ]

    # یافتن اولین سند مثبت در رتبه‌بندی
    top1_label = labels[ sorted_indices[ 0 ] ]
    precision_at_1 = top1_label == 1

    rank = None
    for i, idx in enumerate( sorted_indices ):
        if labels[ idx ] == 1:
            rank = i + 1          # ۱‑indexed
            break
    mrr = 1.0 / rank if rank else 0.0

    # میانگین شباهت‌ها
    mean_sim_pos = float( np.mean( sims[ :len( pos_vecs ) ] ) ) if pos_vecs else 0.0
    mean_sim_neg = float( np.mean( sims[ -len( neg_vecs ): ] ) ) if neg_vecs else 0.0

    return {
        "precision@1": precision_at_1,
        "rank": rank,
        "mrr": mrr,
        "mean_sim_pos": mean_sim_pos,
        "mean_sim_neg": mean_sim_neg,
        "top_sim": sims[ sorted_indices[ 0 ] ],
        "top_label": "positive" if top1_label else "negative"
    }


# ── داده‌های آزمون ─────────────────────────────
def build_test_suite() -> List[ Tuple[ str, str, List[ str ], List[ str ] ] ]:
    """ساخت مجموعه تست شامل دسته‌بندی‌های چالشی"""
    tests = [
          # ۱. Paraphrase (تنوع واژگانی)
        ( "تنوع واژگانی", "لپ‌تاپ سبک با شارژدهی بالا", [ "نوتبوک ۱ کیلویی با باتری ۱۰ ساعته" ], [ "مانیتور ۲۷ اینچ با وضوح 4K" ] ),
        ( "تنوع واژگانی", "کفش مناسب دویدن روزانه", [ "کفش ورزشی سبک با رویه تنفس‌پذیر و کفی نرم" ], [ "صندل چرمی مجلسی زنانه" ] ),

          # ۲. خطای املایی/تایپی
        (
            "خطای املایی",
            "دوربین کانن",          # اشتباه: کانن
            [ "دوربین کانن EOS 2000D" ],
            [ "گوشی سامسونگ گلکسی" ] ),
        (
            "خطای املایی",
            "لب تاب گیمینگ",          # اشتباه فاصله‌گذاری
            [ "لپ‌تاپ گیمینگ با گرافیک RTX 4060" ],
            [ "کنسول بازی پلی‌استیشن ۵" ] ),

          # ۳. زبان عامیانه و کوچه‌بازاری
        ( "عامیانه", "گوشی که حال کنی باهاش بازی کنی و هنگ نکنه", [ "موبایل گیمینگ با پردازندهٔ سریع و رم بالا" ],
          [ "هدفون بی‌سیم ضدآب" ] ),
        ( "عامیانه", "بچه‌م اتاقش سرده دنبال یه وسیله گرمایشی کم مصرف می‌گردم", [ "بخاری برقی کم‌مصرف با ترموستات" ],
          [ "کولر گازی پنجره‌ای" ] ),

          # ۴. پرسش‌های ضمنی / مفهومی
        ( "مفهوم ضمنی", "می‌خوام از بچم عکسای خوب بگیرم تو خونه", [ "دوربین با حالت پرتره و فوکوس خودکار روی صورت" ],
          [ "اسپیکر قابل حمل بلوتوثی" ] ),
        ( "مفهوم ضمنی", "هوای خونه خشکه و صبحا گلو درد دارم", [ "دستگاه بخور سرد اولتراسونیک" ], [ "پنکه رومیزی کوچک" ] ),

          # ۵. جملات منفی / استثنا
        ( "منفی‌سازی", "گوشی غیر آیفون با دوربین خوب", [ "سامسونگ گلکسی با لنز ۵۰ مگاپیکسلی" ],
          [ "آیفون ۱۵ پرو با دوربین ۴۸ مگاپیکسلی" ] ),
        ( "منفی‌سازی", "لباس زمستونی به غیر از پشم", [ "پارچه حوله‌ای گرم و نخی" ], [ "پلیور پشمی یقه‌اسکی" ] ),

          # ۶. تمایز محصولات مشابه
        ( "محصولات مشابه", "شارژر ۲۰ واتی سامسونگ", [ "آداپتور ۲۰W Samsung مدل EP-TA200" ], [ "شارژر ۲۵ واتی سامسونگ مدل EP-TA800" ]
         ),
        ( "محصولات مشابه", "آیفون ۱۳ پرو مکس ۲۵۶ گیگ", [ "آیفون ۱۳ پرو مکس حافظه ۲۵۶ گیگابایت" ], [ "آیفون ۱۴ پرو مکس ۲۵۶ گیگابایت"
                                                                                                   ] ),

          # ۷. متن طولانی / پرسروصدا
        ( "نویز طولانی", "یک گوشی هوشمند با عمر باتری عالی که بتونه دوروز بدون شارژ کار کنه", [
            "گوشی با باتری ۶۰۰۰ میلی‌آمپر ساعت و بهینه‌سازی مصرف"
        ], [
            "توضیحات فنی یک لپ‌تاپ با پردازنده Core i7 و ۱۶ گیگ رم و صفحه‌نمایش OLED و اسپیکرهای Harman که برای گیمینگ و تدوین عالی است و وزن آن تنها ۱.۵ کیلوگرم می‌باشد که حمل آن را آسان کرده و دارای کیبورد با نور پس‌زمینه و وبکم Full HD است."
        ] ),
    ]
    return tests


# ── اجرای ارزیابی ─────────────────────────────
def run_advanced_evaluation() -> None:
    settings = get_settings()
    log_message( LG.RETRIEVAL, "🧪 شروع ارزیابی پیشرفته Embedding", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"ONNX: {settings.USE_ONNX}", LogLevel.DEBUG )

    embedder = EmbeddingService()
    test_suite = build_test_suite()

    # جمع‌آوری نتایج کلی
    total_queries = 0
    total_precision_at_1 = 0
    mrr_values: List[ float ] = []
    margin_values: List[ float ] = []
    all_pos_sims: List[ float ] = []
    all_neg_sims: List[ float ] = []

    for category, query, pos_docs, neg_docs in test_suite:
        log_message( LG.RETRIEVAL, f"\n📊 دسته: {category}", LogLevel.INFO )
        log_message( LG.RETRIEVAL, f"   Query: '{query[:80]}...'", LogLevel.DEBUG )

        # تبدیل به بردار
        q_vec = embedder.encode( f"query: {query}", is_query=True )[ 0 ]
        pos_vecs = [ embedder.encode( f"passage: {doc}", is_query=False )[ 0 ] for doc in pos_docs ]
        neg_vecs = [ embedder.encode( f"passage: {doc}", is_query=False )[ 0 ] for doc in neg_docs ]

        # ارزیابی
        result = evaluate_retrieval( q_vec, pos_vecs, neg_vecs )
        total_queries += 1
        total_precision_at_1 += int( result[ "precision@1" ] )
        mrr_values.append( result[ "mrr" ] )
        margin_values.append( result[ "mean_sim_pos" ] - result[ "mean_sim_neg" ] )
        all_pos_sims.append( result[ "mean_sim_pos" ] )
        all_neg_sims.append( result[ "mean_sim_neg" ] )

        # لاگ جزئیات
        log_message(
            LG.RETRIEVAL, f"   Precision@1: {'✅' if result['precision@1'] else '❌'} | "
            f"Top رتبه: {result['top_label']} (sim={result['top_sim']:.3f}) | "
            f"رتبه اولین مثبت: {result['rank']} | MRR: {result['mrr']:.3f}", LogLevel.DEBUG )
        log_message(
            LG.RETRIEVAL, f"   میانگین شباهت مثبت: {result['mean_sim_pos']:.3f} | "
            f"منفی: {result['mean_sim_neg']:.3f} | "
            f"حاشیه: {result['mean_sim_pos'] - result['mean_sim_neg']:.3f}", LogLevel.DEBUG )

    # ── گزارش نهایی ───────────────────────────
    avg_precision_at_1 = total_precision_at_1 / total_queries if total_queries else 0.0
    avg_mrr = float( np.mean( mrr_values ) ) if mrr_values else 0.0
    avg_margin = float( np.mean( margin_values ) ) if margin_values else 0.0
    mean_pos_sim = float( np.mean( all_pos_sims ) ) if all_pos_sims else 0.0
    mean_neg_sim = float( np.mean( all_neg_sims ) ) if all_neg_sims else 0.0

    log_message( LG.RETRIEVAL, "\n" + "=" * 60, LogLevel.INFO )
    log_message( LG.RETRIEVAL, "            📈 نتایج ارزیابی پیشرفته Embedding", LogLevel.INFO )
    log_message( LG.RETRIEVAL, "=" * 60, LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"🔢 تعداد پرس‌وجوها: {total_queries}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"🎯 Precision@1: {avg_precision_at_1:.2%} ({total_precision_at_1}/{total_queries})", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"📊 Mean Reciprocal Rank (MRR): {avg_mrr:.3f}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"📏 میانگین حاشیه (pos-neg): {avg_margin:.3f}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"🔹 میانگین شباهت مثبت: {mean_pos_sim:.3f}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, f"🔸 میانگین شباهت منفی: {mean_neg_sim:.3f}", LogLevel.INFO )

    # آستانه‌بندی برای آمادگی مدل
    if avg_precision_at_1 >= 0.9 and avg_mrr >= 0.95 and avg_margin > 0.2:
        status = "✅ آمادهٔ استفاده در Production"
    elif avg_precision_at_1 >= 0.7 and avg_margin > 0.1:
        status = "⚠️  قابل قبول، اما نیاز به بهبود دارد"
    else:
        status = "❌ کیفیت ناکافی؛ مدل یا prompt نیاز به بازبینی دارد"

    log_message( LG.RETRIEVAL, f"\n🏁 وضعیت نهایی: {status}", LogLevel.INFO )
    log_message( LG.RETRIEVAL, "=" * 60 + "\n", LogLevel.INFO )


if __name__ == "__main__":
    run_advanced_evaluation()
