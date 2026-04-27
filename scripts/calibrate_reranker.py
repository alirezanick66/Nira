"""‫کالیبراسیون آستانه RerankerService - فیچر MVP Refinement #3

‫هدف: یافتن مقدار بهینه `RERANKER_MIN_SCORE` بر اساس داده واقعی تا تعادل
‫Precision و Recall در Top-3 برقرار شود.

‫نحوه کار:
1. مجموعه‌ای از کوئری‌های نمونه با لیبل «relevant_ids» (استاندارد طلایی)
2. اجرای Hybrid Retrieval برای هر کوئری
3. اجرای rerank_with_scores روی نتایج
4. محاسبه Precision@3 و Recall@3 در آستانه‌های مختلف (0.0 تا 0.5)
5. انتخاب آستانه‌ای که F1 را بیشینه می‌کند

‫خروجی: گزارش JSON با آستانه‌های مختلف + مقدار توصیه‌شده برای settings.

‫نحوه اجرا:
    uv run python scripts/calibrate_reranker.py --output data/reports/reranker_calibration.json

‫نکته: اگر داده‌ی طلایی نباشد، اسکریپت می‌تواند با حالت --self-supervised
‫از خود نتایج Hybrid Search به‌عنوان شبه-لیبل استفاده کند (تخمین پایه).
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import argparse
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.config.settings import get_settings
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.services.reranker_service import RerankerService

#───────────────────── Default Test Set ─────────────────────
# ‫مجموعه پیش‌فرض - برای کالیبراسیون اولیه. کاربر می‌تواند با --dataset فایل JSON بدهد.
DEFAULT_QUERIES: list[ dict[ str, Any ] ] = [
    {
        "query": "گوشی گیمینگ با رم بالا زیر 30 میلیون",
        "relevant_tags": [ "gaming" ],
        "expected_min_ram": 8,
    },
    {
        "query": "گوشی ارزان با دوربین خوب",
        "relevant_tags": [ "photography" ],
        "expected_price_range": "budget",
    },
    {
        "query": "آیفون پرچم‌دار",
        "relevant_brand": "اپل",
        "expected_price_range": "flagship",
    },
    {
        "query": "هندزفری بی‌سیم با باتری قوی",
        "relevant_tags": [ "battery_heavy" ],
    },
    {
        "query": "گوشی سامسونگ زیر 20 میلیون",
        "relevant_brand": "سامسونگ",
    },
]

# ‫آستانه‌های نمونه برای جاروب
THRESHOLD_GRID: list[ float ] = [ 0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50 ]


@dataclass
class ThresholdMetrics:
    """‫معیارهای کالیبراسیون برای یک آستانه"""
    threshold: float
    precision: float
    recall: float
    f1: float
    avg_results_count: float


#───────────────────── Helper Functions ─────────────────────
def _is_relevant( payload: QdrantProductPayload, criterion: dict[ str, Any ] ) -> bool:
    """‫بررسی می‌کند که آیا یک محصول با معیارهای کوئری تطابق دارد.

    ‫KISS: یک محصول «relevant» است اگر حداقل یکی از معیارها را پاس کند.
    """
    matches: list[ bool ] = []

    if "relevant_tags" in criterion:
        wanted_tags = set( criterion[ "relevant_tags" ] )
        matches.append( bool( wanted_tags & set( payload.tags ) ) )

    if "relevant_brand" in criterion:
        matches.append( payload.brand == criterion[ "relevant_brand" ] )

    if "expected_price_range" in criterion:
        matches.append( payload.price_range == criterion[ "expected_price_range" ] )

    if "expected_min_ram" in criterion:
        matches.append( bool( payload.ram_gb and payload.ram_gb >= criterion[ "expected_min_ram" ] ) )

    if not matches: return True          # بدون معیار → همه relevant فرض می‌شوند
    return any( matches )


def _evaluate_threshold(
    query_results: list[ tuple[ list[ tuple[ QdrantProductPayload, float ] ], dict[ str, Any ] ] ],
    threshold: float,
    top_k: int = 3,
) -> ThresholdMetrics:
    """‫محاسبه Precision/Recall در یک آستانه روی همه کوئری‌ها"""
    total_precision = 0.0
    total_recall = 0.0
    total_count = 0
    n_queries = len( query_results )

    for scored, criterion in query_results:
        # ‫فیلتر بر اساس آستانه
        passed = [ ( p, s ) for p, s in scored if s >= threshold ][ :top_k ]
        if not passed:
            # ‫بدون نتیجه → precision=0, recall=0
            continue

        relevant_count = sum( 1 for p, _ in passed if _is_relevant( p, criterion ) )
        total_relevant_in_pool = sum( 1 for p, _ in scored if _is_relevant( p, criterion ) )

        precision = relevant_count / len( passed )
        recall = relevant_count / total_relevant_in_pool if total_relevant_in_pool else 1.0

        total_precision += precision
        total_recall += recall
        total_count += len( passed )

    avg_p = total_precision / n_queries if n_queries else 0.0
    avg_r = total_recall / n_queries if n_queries else 0.0
    f1 = ( 2 * avg_p * avg_r / ( avg_p + avg_r ) ) if ( avg_p + avg_r ) > 0 else 0.0

    return ThresholdMetrics(
        threshold=threshold,
        precision=round( avg_p, 4 ),
        recall=round( avg_r, 4 ),
        f1=round( f1, 4 ),
        avg_results_count=round( total_count / n_queries, 2 ) if n_queries else 0.0,
    )


def calibrate(
    queries: list[ dict[ str, Any ] ],
    top_k: int = 3,
    pool_size: int = 20,
) -> dict[ str, Any ]:
    """‫اجرای کامل پروسه کالیبراسیون

    Returns:
        دیکشنری شامل metrics برای همه آستانه‌ها + recommended_threshold
    """
    log_message( LG.RETRIEVAL, "🎯 شروع کالیبراسیون Reranker...", LogLevel.INFO )

    nlu = NLUPipeline()
    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    # ‫مرحله 1: اجرای retrieval + reranking برای همه کوئری‌ها (یک‌بار)
    query_results: list[ tuple[ list[ tuple[ QdrantProductPayload, float ] ], dict[ str, Any ] ] ] = []

    for case in queries:
        query = case[ "query" ]
        log_message( LG.RETRIEVAL, f"🔹 Query: {query}", LogLevel.DEBUG )

        nlu_result = nlu.process( query )
        candidates = retriever.search(
            query=nlu_result.semantic_query,
            filters=nlu_result.metadata_filters,
            top_k=pool_size,
        )

        if not candidates:
            log_message( LG.RETRIEVAL, f"⚠️ بدون نتیجه برای: {query}", LogLevel.WARNING )
            continue

        scored = reranker.rerank_with_scores( query=query, payloads=candidates )
        query_results.append( ( scored, case ) )

    if not query_results:
        log_message( LG.RETRIEVAL, "❌ هیچ کوئری نتیجه نداد - کالیبراسیون لغو شد", LogLevel.ERROR )
        return { "error": "no_query_results" }

    # ‫مرحله 2: ارزیابی هر آستانه
    metrics_list: list[ ThresholdMetrics ] = []
    for thr in THRESHOLD_GRID:
        m = _evaluate_threshold( query_results, threshold=thr, top_k=top_k )
        metrics_list.append( m )
        log_message(
            LG.RETRIEVAL,
            f"  📊 thr={m.threshold:.2f} | P={m.precision:.3f} | R={m.recall:.3f} | F1={m.f1:.3f} | n={m.avg_results_count:.1f}",
            LogLevel.INFO,
        )

    # ‫مرحله 3: انتخاب بهترین آستانه (Max F1)
    best = max( metrics_list, key=lambda m: m.f1 )

    report: dict[ str, Any ] = {
        "n_queries": len( query_results ),
        "top_k": top_k,
        "pool_size": pool_size,
        "metrics": [ asdict( m ) for m in metrics_list ],
        "recommended_threshold": best.threshold,
        "best_f1": best.f1,
    }

    log_message(
        LG.RETRIEVAL,
        f"🏆 آستانه پیشنهادی: {best.threshold:.2f} (F1={best.f1:.3f})",
        LogLevel.INFO,
    )
    return report


#───────────────────── Entry Point ─────────────────────
def main() -> None:
    parser = argparse.ArgumentParser( description="کالیبراسیون آستانه RerankerService" )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        help="‫مسیر فایل JSON با لیست کوئری‌ها (در غیر این صورت از مجموعه پیش‌فرض استفاده می‌شود)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path( "data/reports/reranker_calibration.json" ),
        help="مسیر فایل خروجی گزارش",
    )
    parser.add_argument( "--top-k", type=int, default=3, help="تعداد نتایج Top-k" )
    parser.add_argument( "--pool-size", type=int, default=20, help="حداکثر تعداد نتایج retrieval" )
    args = parser.parse_args()

    # ‫بارگذاری دیتاست
    if args.dataset and args.dataset.exists():
        with args.dataset.open( "r", encoding="utf-8" ) as f:
            queries = json.load( f )
        log_message( LG.RETRIEVAL, f"📂 {len(queries)} کوئری از {args.dataset}", LogLevel.INFO )
    else:
        queries = DEFAULT_QUERIES
        log_message( LG.RETRIEVAL, f"📂 استفاده از {len(queries)} کوئری پیش‌فرض", LogLevel.INFO )

    # ‫اجرای کالیبراسیون
    report = calibrate( queries=queries, top_k=args.top_k, pool_size=args.pool_size )

    # ‫ذخیره گزارش
    args.output.parent.mkdir( parents=True, exist_ok=True )
    with args.output.open( "w", encoding="utf-8" ) as f:
        json.dump( report, f, ensure_ascii=False, indent=2 )

    settings = get_settings()
    log_message(
        LG.RETRIEVAL,
        f"✅ گزارش ذخیره شد: {args.output}\n"
        f"💡 مقدار فعلی RERANKER_MIN_SCORE: {settings.RERANKER_MIN_SCORE} → پیشنهاد: {report.get('recommended_threshold')}",
        LogLevel.INFO,
    )


if __name__ == "__main__":
    main()
