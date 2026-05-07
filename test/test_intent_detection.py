""" ‫ارزیابی جامع تشخیص نیت (Hybrid: Rule → Semantic Fallback)
‫این ماژول کوئری‌های چالشی را به NLUPipeline تزریق کرده و دقت تشخیص، مسیر اجرا
‫و آستانه‌های معناری را می‌سنجد. قابل اجرا به صورت standalone.
"""
from __future__ import annotations
import sys
from pathlib import Path
from dataclasses import dataclass

sys.path.insert( 0, str( Path( __file__ ).resolve().parents[ 1 ] ) )

from src.config.logging_config import log_message, LogLevel, LG
from src.services.embedding_service import EmbeddingService


@dataclass( frozen=True )
class IntentTestCase:
    query: str
    expected_intent: str
    description: str


def build_test_suite() -> list[ IntentTestCase ]:
    """ساخت مجموعه تست شامل دسته‌بندی‌های چالشی و مرزی"""
    return [
          # Greeting
        IntentTestCase( "سلام", "greeting", "رسمی پایه" ),
        IntentTestCase( "حالت چطوره؟", "greeting", "محاوره‌ای" ),
        IntentTestCase( "روزت بخیر", "greeting", "زمان‌محور" ),
        IntentTestCase( "خسته نباشید داداش", "greeting", "ترکیبی محاوره‌ای" ),
        IntentTestCase( "سلام، یه گوشی ارزون میخوام", "search", "ترکیبی با نیاز جستجو (باید search باشد)" ),

          # Refine
        IntentTestCase( "یه چیز ارزونتر نشون بده", "refine", "اصلاح قیمت" ),
        IntentTestCase( "گزینه بعدی رو بگو", "refine", "پیمایش نتایج" ),
        IntentTestCase( "سبکترش رو میخوام", "refine", "فیلتر وزنی" ),

          # Compare
        IntentTestCase( "فرق این دوتا چیه", "compare", "مقایسه مستقیم" ),
        IntentTestCase( "کدوم بهتره سامسونگ یا شیائومی", "compare", "مقایسه برندی" ),

          # Search (Negative Control & Edge Cases)
        IntentTestCase( "گوشی سامسونگ زیر ۲۰ میلیون", "search", "جستجوی استاندارد" ),
        IntentTestCase( "آیفون ۱۳ پرو مکس ۲۵۶ گیگ", "search", "محصول خاص" ),
        IntentTestCase( "گوشی غیر آیفون با دوربین قوی", "search", "جستجوی منفی‌ساز" ),
        IntentTestCase( "باتری ضعیف ولی قیمت پایین", "search", "کوئری متناقض" ),
        IntentTestCase( "یه لپ‌تاپ خوب برای ترید", "search", "نیاز ضمنی/دامنه خارجی" ),
          # ‫کوئری‌هایی که باید search بمونن ولی ریسک false positive دارن
        IntentTestCase( "سلام، گوشی سامسونگ نشون بده", "search", "شروع با 'سلام' — شبیه احوالپرسی" ),
        IntentTestCase( "چطوره این گوشی؟", "search", "سوال درباره محصول — نه احوالپرسی" ),
        IntentTestCase( "اوضاع دوربینش چطوره", "search", "اوضاع به عنوان توصیف محصول" ),
        IntentTestCase( "حال گوشی‌های اندروید چطوره", "search", "حال در متن محصول" ),
          # compare edge cases
        IntentTestCase( "سامسونگ یا شیائومی؟", "compare", "مقایسه بدون کلمه کلیدی صریح" ),
    ]


def run_evaluation() -> None:
    log_message( LG.NLU, "🧪 شروع ارزیابی جامع تشخیص نیت (Hybrid Intent Detection)", LogLevel.INFO )

    embedder = EmbeddingService()
    nlu = NLUPipeline( domain="mobile", embedding_service=embedder )
    suite = build_test_suite()

    total = len( suite )
    correct = 0
    false_positives: list[ tuple[ IntentTestCase, str ] ] = []
    false_negatives: list[ tuple[ IntentTestCase, str ] ] = []

    for case in suite:
        result = nlu.process( case.query )
        actual = result.intent
        is_correct = ( actual == case.expected_intent )

        status_emoji = "✅" if is_correct else "❌"
        log_message(
            LG.NLU,
            f"{status_emoji} Query: '{case.query}' | Expected: {case.expected_intent} | Actual: {actual} | ({case.description})",
            LogLevel.INFO )

        if is_correct:
            correct += 1
        else:
            if case.expected_intent == "search":
                false_positives.append( ( case, actual ) )
            else:
                false_negatives.append( ( case, actual ) )

    accuracy = ( correct / total ) * 100 if total else 0.0
    log_message( LG.NLU, "\n" + "=" * 60, LogLevel.INFO )
    log_message( LG.NLU, f"📊 نتایج ارزیابی تشخیص نیت", LogLevel.INFO )
    log_message( LG.NLU, f"🔢 تعداد کل کوئری‌ها: {total}", LogLevel.INFO )
    log_message( LG.NLU, f"🎯 دقت کلی: {accuracy:.2f}% ({correct}/{total})", LogLevel.INFO )

    if false_negatives:
        log_message( LG.NLU, "⚠️ عدم تشخیص (False Negatives):", LogLevel.WARNING )
        for case, _ in false_negatives:
            log_message( LG.NLU, f"   - '{case.query}' (انتظار: {case.expected_intent})", LogLevel.WARNING )

    if false_positives:
        log_message( LG.NLU, "⚠️ تشخیص کاذب (False Positives):", LogLevel.WARNING )
        for case, actual in false_positives:
            log_message( LG.NLU, f"   - '{case.query}' (انتظار: {case.expected_intent} | دریافتی: {actual})", LogLevel.WARNING )
    log_message( LG.NLU, "=" * 60 + "\n", LogLevel.INFO )

    run_score_report( nlu, suite )


def run_score_report( nlu: NLUPipeline, suite: list[ IntentTestCase ] ) -> None:
    """ ‫نمایش similarity score هر کوئری برای کالیبراسیون threshold"""
    log_message( LG.NLU, "\n📐 Score Report (برای کالیبراسیون threshold):", LogLevel.INFO )
    for case in suite:
        scores = nlu.get_intent_scores( case.query )
        scores_str = " | ".join( f"{k}: {v:.3f}" for k, v in sorted( scores.items(), key=lambda x: -x[ 1 ] ) )
        log_message( LG.NLU, f"  '{case.query}' → {scores_str}", LogLevel.INFO )


if __name__ == "__main__":
    run_evaluation()
