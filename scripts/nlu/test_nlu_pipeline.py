"""اسکریپت تست خط لوله NLU روی سناریوهای واقعی فارسی"""
from src.core.nlu.nlu_pipeline import NLUPipeline
from src.config.logging_config import log_message, LogLevel, LG


def main() -> None:
    log_message( LG.NLU, "🧪 شروع تست NLU Pipeline...", LogLevel.INFO )

    test_cases = [
        "سلام خوبی؟", "یه گوشی  ارزون میخوام برای عکاسی", "گوشی گیمینگ با رم بالا زیر 30 میلیون تومان",
        "بین آیفون 15 و سامسونگ S24 کدوم بهتره؟", "یه چیز گرونتر ولی با باتری قویتر نشون بده",
        "دوربین عالی برای عکاسی شب و قیمت مناسب"
    ]

    # ✅ نمونه‌سازی استاندارد (بدون وابستگی به Singleton سراسری)
    nlu = NLUPipeline()

    for query in test_cases:
        log_message( LG.NLU, f"🔹 ورودی: {query}", LogLevel.INFO )
        result = nlu.process( query )

        log_message( LG.NLU, f"   🎯 Intent: {result.intent} | IsGreeting: {result.is_greeting}", LogLevel.DEBUG )
        log_message( LG.NLU, f"   📝 Semantic: {result.semantic_query[:50]}...", LogLevel.DEBUG )
        log_message( LG.NLU, f"   🔒 Filters: {result.metadata_filters}", LogLevel.DEBUG )
        log_message( LG.NLU, "-" * 60, LogLevel.DEBUG )


if __name__ == "__main__":
    main()
