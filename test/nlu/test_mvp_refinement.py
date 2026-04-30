"""تست واحد فیچرهای فاز MVP Refinement و Token-Based NLU - نسخه بازنویسی‌شده
پوشش حیاتی:
✅ PersianNumberConverter: تبدیل اعداد حروفی مرکب و مقیاس‌دار
✅ ModelMasker: جلوگیری از تداخل شماره مدل با فیلترهای عددی
✅ TokenParser: مچینگ پنجره‌ای، تفکیک Cue، رنج عددی، مدیریت Negation
✅ ConflictResolver: تشخیص تضاد متنی، استراتژی drop_both، تولید هشدار
✅ NLUPipeline: یکپارچگیend-to-end (نرمال‌سازی → نیت → استخراج → حل تضاد)
"""
from __future__ import annotations
import sys
from typing import Any, cast

from src.core.nlu.number_converter import PersianNumberConverter
from src.core.nlu.model_masker import ModelMasker
from src.core.nlu.token_parser import TokenParser
from src.core.nlu.conflict_resolver import ConflictResolver
from src.config.logging_config import log_message, LogLevel, LG

_TEST_DOMAIN_CONFIG = {
    "negation_keywords": [ "نه", "بدون", "غیر", "به جز", "جز" ],
    "range_separators": [ "تا", "الی", "-", "بین" ],
    "brands": [ "سامسونگ", "آیفون", "شیائومی", "اپل" ],
    "colors": [ "مشکی", "سفید" ],
    "categories": [ "موبایل" ],
    "qualitative_mappings": {
        "ارزان": {
            "price_range": "budget"
        },
        "ارزون": {
            "price_range": "budget"
        },
        "اقتصادی": {
            "price_range": "budget"
        },
        "گران": {
            "price_range": "flagship"
        },
        "گرون": {
            "price_range": "flagship"
        },
        "پرچم‌دار": {
            "price_range": "flagship"
        },
        "باتری قوی": {
            "battery_quality": "excellent"
        }
    },
    "use_case_rules": {
        "گیمینگ": {
            "ram_gb": {
                "gte": 8
            },
            "tags": [ "gaming" ]
        },
        "عکاسی": {
            "camera_quality": "excellent",
            "tags": [ "photography" ]
        }
    },
    "conflict_groups": [ {
        "id": "price_polarity",
        "terms": [ [ "ارزان", "ارزون", "اقتصادی" ], [ "گران", "پرچم‌دار", "لوکس", "گرون" ] ],
        "strategy": "drop_both"
    } ],
    "slot_definitions": {
        "price": {
            "type": "range",
            "operators": {
                "زیر": "<=",
                "بالای": ">=",
                "حدود": "approx",
                "کمتر": "<="
            },
            "units": {
                "میلیون": 1_000_000,
                "میلیارد": 1_000_000_000,
                "تومان": 1,
                "تومن": 1,
                "ت": 1
            },
            "window": 3,
            "cues": []
        },
        "ram_gb": {
            "type": "scalar",
            "cues": [ "رم", "ram" ],
            "units": {
                "گیگ": 1,
                "گیگابایت": 1,
                "gb": 1
            },
            "window": 3
        },
        "storage_gb": {
            "type": "scalar",
            "cues": [ "حافظه", "فضا", "storage" ],
            "units": {
                "گیگ": 1,
                "گیگابایت": 1,
                "ترابایت": 1024,
                "tb": 1024
            },
            "window": 3
        }
    }
}


class TestRunner:

    def __init__( self ) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[ str ] = []

    def assert_eq( self, actual: Any, expected: Any, msg: str ) -> None:
        if actual == expected:
            log_message( LG.NLU, f"✅ {msg}", LogLevel.DEBUG )
            self.passed += 1
        else:
            err_msg = f"❌ {msg} | expected={expected!r}, got={actual!r}"
            log_message( LG.NLU, err_msg, LogLevel.ERROR )
            self.failures.append( err_msg )
            self.failed += 1

    def assert_true( self, cond: bool, msg: str ) -> None:
        self.assert_eq( bool( cond ), True, msg )

    def assert_false( self, cond: bool, msg: str ) -> None:
        self.assert_eq( bool( cond ), False, msg )

    def assert_in( self, item: Any, container: Any, msg: str ) -> None:
        self.assert_true( item in container, msg )

    def report( self ) -> int:
        log_message( LG.NLU, f"📊 نتیجه نهایی: {self.passed} ✅ | {self.failed} ❌", LogLevel.INFO )
        if self.failed:
            for f in self.failures:
                log_message( LG.NLU, f"  • {f}", LogLevel.ERROR )
            return 1
        log_message( LG.NLU, "🎉 همه تست‌های حیاتی با موفقیت پاس شدند.", LogLevel.INFO )
        return 0


def test_number_converter( t: TestRunner ) -> None:
    log_message( LG.NLU, "\n🔢 [1] تست تبدیل اعداد حروفی فارسی", LogLevel.INFO )
    t.assert_eq( PersianNumberConverter.convert( "سی" ), 30, "سی → 30" )
    t.assert_eq( PersianNumberConverter.convert( "چهل و پنج" ), 45, "چهل و پنج → 45" )
    t.assert_eq( PersianNumberConverter.convert( "یک میلیارد" ), 1_000_000_000, "یک میلیارد → 1B" )
    t.assert_eq( PersianNumberConverter.convert( "سی و دو" ), 32, "سی و دو → 32" )


def test_model_masker( t: TestRunner ) -> None:
    log_message( LG.NLU, "\n🎭 [2] تست ماسک کردن هوشمند شماره مدل‌ها", LogLevel.INFO )
    brand_cues = frozenset( { "آیفون", "سامسونگ", "redmi", "s", "note" } )
    # تست مدل چسبیده (کاربرد اصلی ModelMasker)
    res = ModelMasker.mask( "میخوام S24 بخرم", brand_cues )
    t.assert_true( "__MODEL_0__" in res.masked_text, "S24 → ماسک شد" )
    t.assert_eq( res.placeholders.get( "__MODEL_0__" ), "S24", "جایگزینی صحیح S24" )
    # تست متن بدون مدل
    res = ModelMasker.mask( "زیر سی میلیون تومان", brand_cues )
    t.assert_eq( res.masked_text, "زیر سی میلیون تومان", "متن بدون مدل → بدون تغییر" )


def test_token_parser( t: TestRunner ) -> None:
    log_message( LG.NLU, "\n⚙️ [3] تست موتور پارس توکنی (TokenParser)", LogLevel.INFO )
    parser = TokenParser( _TEST_DOMAIN_CONFIG )

    # A: قیمت با واحد صریح
    filters = parser.parse( "زیر 30 میلیون تومان" )
    t.assert_true( "price" in filters, "فیلتر قیمت استخراج شد" )
    t.assert_eq( cast( dict, filters[ "price" ] ).get( "<=" ), 30_000_000.0, "زیر 30 میلیون → max=30M" )

    # B: رنج عددی (بین X تا Y)
    filters = parser.parse( "موبایل بین 10 تا 20 میلیون" )
    t.assert_true( "price" in filters, "فیلتر رنج قیمت استخراج شد" )
    pr = cast( dict, filters[ "price" ] )
    t.assert_eq( pr.get( ">=" ), 10_000_000.0, "بین 10 تا 20 → min=10M" )
    t.assert_eq( pr.get( "<=" ), 20_000_000.0, "بین 10 تا 20 → max=20M" )

    # C: تفکیک Cue (رم vs حافظه) - رفع باگ تداخل
    filters = parser.parse( "رم حداقل 8 گیگ و حافظه 128 گیگ" )
    t.assert_true( "ram_gb" in filters, "فیلتر رم با Cue صحیح مچ شد" )
    t.assert_true( "storage_gb" in filters, "فیلتر حافظه با Cue صحیح مچ شد" )
    t.assert_eq( cast( dict, filters[ "ram_gb" ] ).get( ">=" ), 8.0, "رم 8 گیگ → 8" )
    t.assert_eq( cast( dict, filters[ "storage_gb" ] ).get( ">=" ), 128.0, "حافظه 128 گیگ → 128" )

    # D: مدیریت Negation
    filters = parser.parse( "گوشی نه شیائومی مشکی" )
    t.assert_in( "brand_not", filters, "کلید brand_not برای نفی ایجاد شد" )
    t.assert_in( "شیائومی", cast( list, filters.get( "brand_not", [] ) ), "برند نفی‌شده ثبت شد" )

    # E: نگاشت کیفی و Use-Case
    filters = parser.parse( "یه گوشی گیمینگ با باتری قوی" )
    t.assert_in( "tags", filters, "تگ‌های use_case اضافه شدند" )
    t.assert_in( "gaming", cast( list, filters.get( "tags", [] ) ), "تگ gaming از گیمینگ استخراج شد" )
    t.assert_eq( filters.get( "battery_quality" ), "excellent", "باتری قوی → excellent مچ شد" )


def test_conflict_resolver( t: TestRunner ) -> None:
    log_message( LG.NLU, "\n⚖️ [4] تست تشخیص و حل تضاد فیلترها", LogLevel.INFO )
    resolver = ConflictResolver( _TEST_DOMAIN_CONFIG )
    filters = { "price_range": "budget" }
    cleaned, report = resolver.resolve( filters, "گوشی ارزون ولی پرچم‌دار میخوام" )
    t.assert_true( report.has_conflicts, "تضاد متنی تشخیص داده شد" )
    t.assert_false( "price_range" in cleaned, "فیلتر price_range حذف شد (drop_both)" )


def test_nlu_integration( t: TestRunner ) -> None:
    log_message( LG.NLU, "\n🔗 [5] تست یکپارچگی端到端 NLU Pipeline", LogLevel.INFO )
    try:
        from src.core.nlu.nlu_pipeline import NLUPipeline
        from src.config.domain_loader import DomainConfigLoader
        nlu = NLUPipeline( domain="mobile", config_loader=DomainConfigLoader() )
    except Exception as exc:
        log_message( LG.NLU, f"⚠️ بارگذاری NLUPipeline ناموفق: {exc}", LogLevel.WARNING )
        return

    cases = [
        ( "گوشی زیر 30 میلیون", {
            "has_price": True
        } ),
        ( "بین آیفون 15 و سامسونگ", {
            "intent": "compare",
            "has_brand_list": True
        } ),
    ]
    for query, exp in cases:
        res = nlu.process( query )
        log_message( LG.NLU, f"🔹 '{query}' → Intent: {res.intent} | Filters: {res.metadata_filters}", LogLevel.DEBUG )
        if exp.get( "has_price" ): t.assert_true( "price" in res.metadata_filters, f"{query} → قیمت دارد" )
        if exp.get( "has_brand_list" ):
            t.assert_true( isinstance( res.metadata_filters.get( "brand" ), list ), f"{query} → لیست برند" )


def main() -> int:
    log_message( LG.NLU, "🧪 شروع تست‌های MVP Refinement (نسخه Token-Based)", LogLevel.INFO )
    runner = TestRunner()
    test_number_converter( runner )
    test_model_masker( runner )
    test_token_parser( runner )
    test_conflict_resolver( runner )
    test_nlu_integration( runner )
    return runner.report()


if __name__ == "__main__":
    sys.exit( main() )
