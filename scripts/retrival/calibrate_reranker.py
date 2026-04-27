"""کالیبراسیون آستانه RerankerService
هدف: یافتن مقدار بهینه RERANKER_MIN_SCORE بر اساس داده واقعی تا تعادل
Precision و Recall در Top-3 برقرار شود.
نحوه استفاده: فراخوانی مستقیم تابع calibrate() از کد یا نوت‌بوک.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, NamedTuple

from src.config.logging_config import log_message, LogLevel, LG
from src.config.settings import get_settings
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.core.vector.qdrant_retriever import QdrantHybridRetriever
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.services.reranker_service import RerankerService


# ─────────────────── Type Definitions ───────────────────
class QueryCase( NamedTuple ):
    """یک کوئری تستی به همراه معیارهای relevance مورد انتظار."""
    query: str
    relevant_tags: list[ str ] | None = None
    relevant_brand: str | None = None
    expected_price_range: str | None = None
    expected_min_ram: int | None = None


class ScoredPayload( NamedTuple ):
    payload: QdrantProductPayload
    score: float


# ─────────────────── Defaults ───────────────────
DEFAULT_QUERIES: list[ QueryCase ] = [
    QueryCase( "گوشی گیمینگ با رم بالا زیر 30 میلیون", relevant_tags=[ "gaming" ], expected_min_ram=8 ),
    QueryCase( "گوشی ارزان با دوربین خوب", relevant_tags=[ "photography" ], expected_price_range="budget" ),
    QueryCase( "آیفون پرچم‌دار", relevant_brand="اپل", expected_price_range="flagship" ),
    QueryCase( "هندزفری بی‌سیم با باتری قوی", relevant_tags=[ "battery_heavy" ] ),
    QueryCase( "گوشی سامسونگ زیر 20 میلیون", relevant_brand="سامسونگ" ),
]

DEFAULT_THRESHOLDS = [ 0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50 ]


@dataclass( frozen=True, slots=True )
class ThresholdMetrics:
    """معیارهای کالیبراسیون برای یک آستانه."""
    threshold: float
    precision: float
    recall: float
    f1: float
    avg_results_count: float


# ─────────────────── Core ───────────────────
def calibrate(
        queries: list[ QueryCase ] | None = None,
        *,
        top_k: int = 3,
        pool_size: int = 20,
        thresholds: list[ float ] | None = None,
        output_path: Path = Path( "data/reports/reranker_calibration.json" ),
) -> dict[ str, Any ]:
    """اجرای کامل پروسه کالیبراسیون و ذخیره گزارش."""
    log_message( LG.RETRIEVAL, "🎯 شروع کالیبراسیون Reranker...", LogLevel.INFO )

    cases = queries or DEFAULT_QUERIES
    thr_grid = thresholds or DEFAULT_THRESHOLDS

    nlu = NLUPipeline()
    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    evaluated: list[ tuple[ list[ ScoredPayload ], QueryCase ] ] = []

    for case in cases:
        log_message( LG.RETRIEVAL, f"🔹 Query: {case.query}", LogLevel.DEBUG )
        nlu_result = nlu.process( case.query )

        candidates = retriever.search(
            query=nlu_result.semantic_query,
            filters=nlu_result.metadata_filters,          # type: ignore[arg-type]
            top_k=pool_size,
        )
        if not candidates:
            log_message( LG.RETRIEVAL, f"⚠️ بدون نتیجه برای: {case.query}", LogLevel.WARNING )
            continue

        scored = [ ScoredPayload( p, s ) for p, s in reranker.rerank_with_scores( query=case.query, payloads=candidates ) ]
        evaluated.append( ( scored, case ) )

    if not evaluated:
        log_message( LG.RETRIEVAL, "❌ هیچ کوئری نتیجه نداد - کالیبراسیون لغو شد", LogLevel.ERROR )
        return { "error": "no_query_results" }

    metrics = [ _evaluate_threshold( evaluated, thr, top_k ) for thr in thr_grid ]

    for m in metrics:
        log_message(
            LG.RETRIEVAL,
            f"  📊 thr={m.threshold:.2f} | P={m.precision:.3f} | R={m.recall:.3f} | "
            f"F1={m.f1:.3f} | n={m.avg_results_count:.1f}",
            LogLevel.INFO,
        )

    best = max( metrics, key=lambda m: m.f1 )
    report = {
        "n_queries": len( evaluated ),
        "top_k": top_k,
        "pool_size": pool_size,
        "metrics": [ asdict( m ) for m in metrics ],
        "recommended_threshold": best.threshold,
        "best_f1": best.f1,
    }

    log_message( LG.RETRIEVAL, f"🏆 آستانه پیشنهادی: {best.threshold:.2f} (F1={best.f1:.3f})", LogLevel.INFO )

    output_path.parent.mkdir( parents=True, exist_ok=True )
    output_path.write_text( json.dumps( report, ensure_ascii=False, indent=2 ), encoding="utf-8" )

    settings = get_settings()
    log_message(
        LG.RETRIEVAL,
        f"✅ گزارش ذخیره شد: {output_path}\n"
        f"💡 مقدار فعلی RERANKER_MIN_SCORE: {settings.RERANKER_MIN_SCORE} "
        f"→ پیشنهاد: {report['recommended_threshold']}",
        LogLevel.INFO,
    )
    return report


# ─────────────────── Helpers ───────────────────
def _is_relevant( payload: QdrantProductPayload, case: QueryCase ) -> bool:
    """بررسی می‌کند آیا محصول همه معیارهای تعریف‌شده را برآورده می‌کند (AND)."""
    checks = []
    if case.relevant_tags is not None:
        checks.append( bool( set( case.relevant_tags ) & set( payload.tags ) ) )
    if case.relevant_brand is not None:
        checks.append( payload.brand == case.relevant_brand )
    if case.expected_price_range is not None:
        checks.append( payload.price_range == case.expected_price_range )
    if case.expected_min_ram is not None:
        checks.append( bool( payload.ram_gb and payload.ram_gb >= case.expected_min_ram ) )

    return all( checks ) if checks else True


def _evaluate_threshold(
    evaluated: list[ tuple[ list[ ScoredPayload ], QueryCase ] ],
    threshold: float,
    top_k: int,
) -> ThresholdMetrics:
    """محاسبه Precision/Recall برای یک آستانه روی همه کوئری‌ها."""
    precisions: list[ float ] = []
    recalls: list[ float ] = []
    counts: list[ int ] = []

    for scored, case in evaluated:
        passed = [ r for r in scored if r.score >= threshold ][ :top_k ]
        reachable = sum( 1 for r in scored if _is_relevant( r.payload, case ) and r.score >= threshold )
        rel = sum( 1 for r in passed if _is_relevant( r.payload, case ) )

        if not passed:
            precisions.append( 0.0 )
            counts.append( 0 )
        else:
            precisions.append( rel / len( passed ) )
            counts.append( len( passed ) )

        if reachable == 0:
            continue

        recalls.append( rel / reachable )

    avg_p = sum( precisions ) / len( precisions ) if precisions else 0.0
    avg_r = sum( recalls ) / len( recalls ) if recalls else 0.0
    f1 = ( 2 * avg_p * avg_r / ( avg_p + avg_r ) ) if ( avg_p + avg_r ) > 0 else 0.0

    return ThresholdMetrics(
        threshold=round( threshold, 2 ),
        precision=round( avg_p, 4 ),
        recall=round( avg_r, 4 ),
        f1=round( f1, 4 ),
        avg_results_count=round( sum( counts ) / len( counts ), 2 ) if counts else 0.0,
    )


if __name__ == "__main__":
    calibrate()
