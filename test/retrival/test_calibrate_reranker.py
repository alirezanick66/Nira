"""کالیبراسیون آستانه RerankerService
هدف: یافتن مقدار بهینه RERANKER_MIN_SCORE بر اساس داده واقعی تا تعادل
Precision و Recall در Top-3 برقرار شود.
نحوه استفاده: فراخوانی مستقیم تابع calibrate() از کد یا نوت‌بوک.

اصلاحات کلیدی نسخه فعلی:
1. _is_relevant: مدیریت soft برای فیلدهای None در Payload (جلوگیری از False Negative).
2. اصلاح فرمول Recall (denominator = کل relevantهای داخل pool، نه پس از threshold).
3. هم‌راستاسازی query بین Retriever و Reranker.
4. افزایش pool_size پیش‌فرض برای ایجاد فضای فیلتر.
5. نگاشت برندها (Apple ↔ اپل ↔ آیفون) برای جلوگیری از mismatch.
6. لاگ Diagnostic per-query برای ردیابی کوئری‌های مشکل‌دار.
7. Threshold grid ریزتر تا بهترین نقطه F1 با دقت بیشتر یافت شود.
"""

#───────────────────── imports ─────────────────────
from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, NamedTuple

#───────────────────── local imports ─────────────────────
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

# ✅ Threshold grid ریزتر برای یافتن نقطه بهینه با دقت بیشتر
DEFAULT_THRESHOLDS = [
    0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45,
    0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90,
]

CALIBRATION_DATASET_PATH = Path( "F:/PythonProjects/Nira/data/calibration/calibration_queries.jsonl" )

# ✅ نگاشت نام‌های مترادف برندها (جلوگیری از mismatch بر اثر اسم تجاری vs اسم برند)
_BRAND_ALIASES: dict[ str, set[ str ] ] = {
    "اپل": { "اپل", "آیفون", "apple", "iphone" },
    "سامسونگ": { "سامسونگ", "samsung", "گلکسی", "galaxy" },
    "شیائومی": { "شیائومی", "xiaomi", "redmi", "ردمی" },
    "هواوی": { "هواوی", "huawei", "honor" },
    "وان‌پلاس": { "وان‌پلاس", "وان پلاس", "oneplus" },
    "آنر": { "آنر", "honor" },
    "موتورولا": { "موتورولا", "motorola", "moto" },
    "سونی": { "سونی", "sony", "xperia" },
    "نوکیا": { "نوکیا", "nokia" },
    "گوگل": { "گوگل", "google", "pixel", "پیکسل" },
    "تی‌سی‌ال": { "تی‌سی‌ال", "تی سی ال", "tcl" },
    "ریلمی": { "ریلمی", "realme" },
    "پوکو": { "پوکو", "poco" },
    "بلک بری": { "بلک بری", "blackberry" },
}


def _brand_matches( payload_brand: str | None, expected_brand: str ) -> bool:
    """مطابقت برند با درنظرگرفتن نام‌های مترادف."""
    if not payload_brand:
        return False
    pb = payload_brand.strip().lower()
    eb = expected_brand.strip().lower()
    if pb == eb:
        return True
    # Lookup aliases (هم برای expected هم برای payload)
    for canonical, aliases in _BRAND_ALIASES.items():
        aliases_lower = { a.lower() for a in aliases } | { canonical.lower() }
        if eb in aliases_lower and pb in aliases_lower:
            return True
    return False


@dataclass( frozen=True, slots=True )
class ThresholdMetrics:
    """معیارهای کالیبراسیون برای یک آستانه."""
    threshold: float
    precision: float
    recall: float
    f1: float
    avg_results_count: float
    queries_with_zero_relevant: int = 0          # ‫تعداد کوئری‌هایی که هیچ نتیجه‌ای پاس نشد


@dataclass
class QueryDiagnostic:
    """گزارش تشخیصی برای یک کوئری در pool اولیه (قبل از threshold)."""
    query: str
    pool_size: int
    n_relevant_in_pool: int
    top_score: float
    top_relevant_score: float | None
    score_distribution: list[ float ] = field( default_factory=list )


# ─────────────────── Core ───────────────────
def calibrate(
        queries: list[ QueryCase ] | None = None,
        *,
        top_k: int = 3,
        pool_size: int = 50,                          # ✅ افزایش از 20 → 50 برای فضای فیلتر بیشتر
        thresholds: list[ float ] | None = None,
        output_path: Path = Path( "data/reports/reranker_calibration.json" ),
        use_semantic_query_for_rerank: bool = False,  # ✅ کنترل هم‌راستاسازی query
) -> dict[ str, Any ]:
    """اجرای کامل پروسه کالیبراسیون و ذخیره گزارش."""
    log_message( LG.RETRIEVAL, "🎯 شروع کالیبراسیون Reranker...", LogLevel.INFO )

    cases = queries or DEFAULT_QUERIES
    thr_grid = thresholds or DEFAULT_THRESHOLDS

    nlu = NLUPipeline()
    retriever = QdrantHybridRetriever()
    reranker = RerankerService()

    evaluated: list[ tuple[ list[ ScoredPayload ], QueryCase ] ] = []
    diagnostics: list[ QueryDiagnostic ] = []

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

        # ✅ هم‌راستاسازی query: استفاده از همان متنی که Retriever استفاده کرد
        # ‫یا متن خام بسته به انتخاب کاربر. پیش‌فرض: متن خام (case.query) چون reranker
        # ‫مدلِ cross-encoder هست و context بیشتری از متن خام بهره می‌بره.
        rerank_query = nlu_result.semantic_query if use_semantic_query_for_rerank else case.query

        scored = [ ScoredPayload( p, s ) for p, s in reranker.rerank_with_scores( query=rerank_query, payloads=candidates ) ]
        evaluated.append( ( scored, case ) )

        # ✅ Diagnostic per-query
        relevants_in_pool = [ r for r in scored if _is_relevant( r.payload, case ) ]
        top_relevant_score = max( ( r.score for r in relevants_in_pool ), default=None )
        diag = QueryDiagnostic(
            query=case.query,
            pool_size=len( scored ),
            n_relevant_in_pool=len( relevants_in_pool ),
            top_score=scored[ 0 ].score if scored else 0.0,
            top_relevant_score=top_relevant_score,
            score_distribution=[ round( r.score, 3 ) for r in scored[ :5 ] ],
        )
        diagnostics.append( diag )

        # ‫لاگ کوئری‌های مشکل‌دار (relevant کم در pool)
        if len( relevants_in_pool ) == 0:
            log_message(
                LG.RETRIEVAL,
                f"❗ هیچ relevant در pool برای «{case.query}» (pool={len(scored)}, top_score={diag.top_score:.3f})",
                LogLevel.WARNING,
            )
        elif top_relevant_score is not None and top_relevant_score < 0.1:
            log_message(
                LG.RETRIEVAL,
                f"⚠️ بهترین relevant score پایین برای «{case.query}»: {top_relevant_score:.3f}",
                LogLevel.WARNING,
            )

    if not evaluated:
        log_message( LG.RETRIEVAL, "❌ هیچ کوئری نتیجه نداد - کالیبراسیون لغو شد", LogLevel.ERROR )
        return { "error": "no_query_results" }

    # ✅ آمار کلی pool
    n_with_relevant = sum( 1 for d in diagnostics if d.n_relevant_in_pool > 0 )
    log_message(
        LG.RETRIEVAL,
        f"📈 خلاصه pool: {n_with_relevant}/{len(diagnostics)} کوئری حداقل یک relevant داشتند",
        LogLevel.INFO,
    )

    metrics = [ _evaluate_threshold( evaluated, thr, top_k ) for thr in thr_grid ]

    for m in metrics:
        log_message(
            LG.RETRIEVAL,
            f"  📊 thr={m.threshold:.2f} | P={m.precision:.3f} | R={m.recall:.3f} | "
            f"F1={m.f1:.3f} | n={m.avg_results_count:.1f} | empty={m.queries_with_zero_relevant}",
            LogLevel.INFO,
        )

    # ✅ انتخاب آستانه بهینه: F1 ماکزیمم + tie-breaker با threshold بالاتر
    # ‫(در صورت تساوی F1، آستانه بالاتر را انتخاب کن چون precision بهتری می‌دهد)
    best = max( metrics, key=lambda m: ( m.f1, m.threshold ) )

    report = {
        "n_queries": len( evaluated ),
        "top_k": top_k,
        "pool_size": pool_size,
        "rerank_query_mode": "semantic" if use_semantic_query_for_rerank else "raw",
        "n_queries_with_relevant_in_pool": n_with_relevant,
        "metrics": [ asdict( m ) for m in metrics ],
        "recommended_threshold": best.threshold,
        "best_f1": best.f1,
        "diagnostics": [
            {
                "query": d.query,
                "pool_size": d.pool_size,
                "n_relevant_in_pool": d.n_relevant_in_pool,
                "top_score": round( d.top_score, 4 ),
                "top_relevant_score": round( d.top_relevant_score, 4 ) if d.top_relevant_score is not None else None,
                "top5_scores": d.score_distribution,
            } for d in diagnostics
        ],
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
    """‫بررسی می‌کند آیا محصول معیارهای تعریف‌شده را برآورده می‌کند.

    ‫استراتژی Soft-AND (نسخه اصلاح‌شده):
    - فقط فیلدهایی که در Payload **مقدار معتبر** دارند بررسی می‌شوند.
    - فیلد `None` در Payload به‌منزله «نامشخص» در نظر گرفته می‌شود نه نامعتبر.
    - این جلوگیری می‌کند از False Negative وقتی دیتای ناقص داریم
      (مثلاً ram_gb=None در دیتابیس) که قبلاً باعث ground-truth کوچک می‌شد.
    - اگر هیچ معیار قابل بررسی نباشد و حداقل یک معیار اعلام‌شده باشد، False
      (تا کوئری‌های با criteria کاملاً نامعلوم نتیجه «همه relevant» تولید نکنند).
    """
    declared_count = 0          # ‫تعداد معیارهای اعلام‌شده در QueryCase
    matched_count = 0           # ‫تعداد معیارهای برآورده‌شده
    checkable_count = 0         # ‫تعداد معیارهای قابل بررسی (Payload value موجود است)

    if case.relevant_tags is not None:
        declared_count += 1
        if payload.tags:                # tags لیست خالی → نامشخص
            checkable_count += 1
            if set( case.relevant_tags ) & set( payload.tags ):
                matched_count += 1

    if case.relevant_brand is not None:
        declared_count += 1
        if payload.brand:               # brand=None → نامشخص
            checkable_count += 1
            if _brand_matches( payload.brand, case.relevant_brand ):
                matched_count += 1

    if case.expected_price_range is not None:
        declared_count += 1
        if payload.price_range:         # price_range همیشه ست می‌شود
            checkable_count += 1
            if payload.price_range == case.expected_price_range:
                matched_count += 1

    if case.expected_min_ram is not None:
        declared_count += 1
        if payload.ram_gb is not None:  # ‫ram=None → نامشخص (نه irrelevant)
            checkable_count += 1
            if payload.ram_gb >= case.expected_min_ram:
                matched_count += 1

    # ‫هیچ معیاری اعلام نشده → کل نتایج relevant در نظر گرفته شوند
    if declared_count == 0:
        return True

    # ‫هیچ معیار قابل بررسی‌ای موجود نیست → relevant در نظر گرفته نشود
    # ‫(چون نمی‌توانیم تأیید کنیم محصول واقعاً منطبق است)
    if checkable_count == 0:
        return False

    # ‫AND منطقی: همه معیارهای *قابل بررسی* باید برآورده شوند
    return matched_count == checkable_count


def _evaluate_threshold(
    evaluated: list[ tuple[ list[ ScoredPayload ], QueryCase ] ],
    threshold: float,
    top_k: int,
) -> ThresholdMetrics:
    """محاسبه Precision/Recall برای یک آستانه روی همه کوئری‌ها.

    اصلاحات نسبت به نسخه قبل:
    - Recall denominator اکنون «کل relevantهای داخل pool» است (نه پس از threshold).
      ‫این فرمول استاندارد و صحیح Recall@k است.
    - کوئری‌های بدون هیچ relevant در pool از محاسبه precision/recall کنار گذاشته
      می‌شوند (تا میانگین skew نشود) ولی در شمارنده «empty» ثبت می‌شوند.
    """
    precisions: list[ float ] = []
    recalls: list[ float ] = []
    counts: list[ int ] = []
    queries_with_zero_relevant = 0

    for scored, case in evaluated:
        # ‫کل relevantها در pool (قبل از threshold) — برای recall denominator
        total_relevant_in_pool = sum( 1 for r in scored if _is_relevant( r.payload, case ) )

        # ‫کوئری بدون هیچ relevant در pool → از محاسبه میانگین کنار گذاشته شود
        if total_relevant_in_pool == 0:
            # ‫اگر threshold نتایج خالی برگرداند، در شمارنده ثبت کن
            passed_empty = [ r for r in scored if r.score >= threshold ][ :top_k ]
            if not passed_empty:
                queries_with_zero_relevant += 1
            continue

        # ‫نتایج بالای threshold (Top-K)
        passed = [ r for r in scored if r.score >= threshold ][ :top_k ]

        if not passed:
            # ‫هیچ نتیجه‌ای از threshold نگذشت → P=0, R=0 (عبور برای recall نیز)
            precisions.append( 0.0 )
            recalls.append( 0.0 )
            counts.append( 0 )
            queries_with_zero_relevant += 1
            continue

        # ‫تعداد relevantهای داخل پسرفته (Top-K بالای threshold)
        rel_in_passed = sum( 1 for r in passed if _is_relevant( r.payload, case ) )

        precisions.append( rel_in_passed / len( passed ) )
        counts.append( len( passed ) )

        # ✅ فرمول استاندارد Recall@k:
        # ‫denominator = کل relevantها در pool (محدود به top_k چون کاربر فقط top_k را می‌بیند)
        # ‫این بازتاب درستی از «چه نسبت از relevantهای موجود را به کاربر نشان دادیم» است.
        denom = min( total_relevant_in_pool, top_k )
        recalls.append( rel_in_passed / denom )

    avg_p = sum( precisions ) / len( precisions ) if precisions else 0.0
    avg_r = sum( recalls ) / len( recalls ) if recalls else 0.0
    f1 = ( 2 * avg_p * avg_r / ( avg_p + avg_r ) ) if ( avg_p + avg_r ) > 0 else 0.0

    return ThresholdMetrics(
        threshold=round( threshold, 2 ),
        precision=round( avg_p, 4 ),
        recall=round( avg_r, 4 ),
        f1=round( f1, 4 ),
        avg_results_count=round( sum( counts ) / len( counts ), 2 ) if counts else 0.0,
        queries_with_zero_relevant=queries_with_zero_relevant,
    )


def load_dataset( path: Path ) -> list[ dict[ str, Any ] ]:
    """لود کردن دیتاست از JSON یا JSONL"""
    if not path.exists():
        raise FileNotFoundError( f"فایل دیتاست یافت نشد: {path}" )
    if path.suffix == ".jsonl":
        with path.open( "r", encoding="utf-8" ) as f:
            return [ json.loads( line ) for line in f if line.strip() ]
    with path.open( "r", encoding="utf-8" ) as f:
        return json.load( f )


def dataset_to_querycases( data: list[ dict[ str, Any ] ] ) -> list[ QueryCase ]:
    """تبدیل داده‌های خام دیتاست به لیست QueryCase"""
    cases = []
    for item in data:
        cases.append(
            QueryCase(
                query=item[ "query" ],
                relevant_tags=item.get( "relevant_tags" ),
                relevant_brand=item.get( "relevant_brand" ),
                expected_price_range=item.get( "expected_price_range" ),
                expected_min_ram=item.get( "expected_min_ram" ),
            ) )
    return cases


def run_calibration() -> None:
    """اجرای کالیبراسیون با مقادیر ثابت و بدون نیاز به آرگومان"""
    if not CALIBRATION_DATASET_PATH.exists():
        log_message(
            LG.RETRIEVAL,
            f"⚠️ فایل دیتاست در مسیر {CALIBRATION_DATASET_PATH} یافت نشد. استفاده از کوئری‌های پیش‌فرض.",
            LogLevel.WARNING,
        )
        queries = None
    else:
        raw_data = load_dataset( CALIBRATION_DATASET_PATH )
        queries = dataset_to_querycases( raw_data )

    calibrate( queries=queries, top_k=3, pool_size=50 )


if __name__ == "__main__":
    run_calibration()
