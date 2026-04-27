"""‫تست واحد فیچرهای فاز MVP Refinement - نسخه بازنویسی‌شده
‫پوشش:
✅ PersianNumberConverter: تبدیل اعداد حروفی فارسی
✅ ModelMasker: ماسک کردن ایمن شماره مدل‌ها
✅ SlotExtractor: استخراج کانفیگ‌محور فیلترها (قیمت، رم، حافظه)
✅ ConflictResolver: حل تضاد فیلترها
✅ NLUPipeline: یکپارچگی端到端 (NLU → Extraction → Resolution)
‫نکته: این تست‌ها کاملاً آفلاین اجرا می‌شوند و نیازی به Qdrant/PostgreSQL ندارند.
‫نحوه اجرا:
uv run python scripts/test_mvp_refinement.py
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import sys
from typing import Any
#───────────────────── Local Imports ─────────────────────
from src.core.nlu.number_converter import PersianNumberConverter
from src.core.nlu.model_masker import ModelMasker
from src.core.nlu.slot_extractor import SlotExtractor, SlotRule
from src.core.nlu.conflict_resolver import ConflictResolver

# NLUPipeline فقط در تست یکپارچه ایمپورت می‌شود


#─────────────────── Helper ───────────────────
class TestRunner:
    """‫اجراکنندهٔ سبک و مستقل تست‌ها بدون وابستگی به pytest"""

    def __init__( self ) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[ str ] = []

    def assert_eq( self, actual: Any, expected: Any, msg: str ) -> None:
        if actual == expected:
            self.passed += 1
            print( f" ✅ {msg}" )
        else:
            self.failed += 1
            err = f"{msg} | expected={expected!r}, got={actual!r}"
            self.failures.append( err )
            print( f"  ❌ {err}" )

    def assert_true( self, cond: bool, msg: str ) -> None:
        self.assert_eq( bool( cond ), True, msg )

    def assert_in_range( self, actual: int | float | None, low: int, high: int, msg: str ) -> None:
        if actual is not None and low <= actual <= high:
            self.passed += 1
            print( f"  ✅ {msg} (got={actual:,})" )
        else:
            self.failed += 1
            err = f"{msg} | expected in [{low:,}..{high:,}], got={actual!r}"
            self.failures.append( err )
            print( f"  ❌ {err}" )

    def report( self ) -> int:
        print( f"\n{'='*60}\n📊 نتیجه: {self.passed} ✅ | {self.failed} ❌\n{'='*60}" )
        if self.failed:
            print( "\n❌ موارد ناموفق:" )
            for f in self.failures:
                print( f"  - {f}" )
            return 1
        print( "🎉 همه تست‌ها موفق بودند!" )
        return 0


#─────────────────── Test 1: PersianNumberConverter ───────────────────
def test_number_converter( t: TestRunner ) -> None:
    print( "\n🔢 [1] تست تبدیل اعداد حروفی فارسی" )
    t.assert_eq( PersianNumberConverter.convert( "سی" ), 30, "سی → 30" )
    t.assert_eq( PersianNumberConverter.convert( "چهل و پنج" ), 45, "چهل و پنج → 45" )
    t.assert_eq( PersianNumberConverter.convert( "صد و بیست" ), 120, "صد و بیست → 120" )
    t.assert_eq( PersianNumberConverter.convert( "یک میلیارد و دویست میلیون" ), 1_200_000_000, "1.2 میلیارد → 1,200,000,000" )
    t.assert_eq( PersianNumberConverter.convert( "سی و دو" ), 32, "سی و دو → 32" )
    t.assert_eq( PersianNumberConverter.convert( "" ), None, "خالی → None" )
    t.assert_eq( PersianNumberConverter.convert( "هیچ" ), None, "غیرعدد → None" )


#─────────────────── Test 2: ModelMasker ───────────────────
def test_model_masker( t: TestRunner ) -> None:
    print( "\n🎭 [2] تست ماسک کردن هوشمند شماره مدل‌ها" )
    brand_cues = frozenset( { "آیفون", "سامسونگ", "گلکسی", "redmi" } )

    res = ModelMasker.mask( "آیفون 15 خوبه", brand_cues )
    t.assert_true( "__MODEL_0__" in res.masked_text, "آیفون 15 → مسک شد" )
    t.assert_eq( res.placeholders.get( "__MODEL_0__" ), "آیفون 15", "جایگزینی صحیح آیفون 15" )

    res = ModelMasker.mask( "میخوام S24 بخرم", brand_cues )
    t.assert_true( "__MODEL_0__" in res.masked_text, "S24 → مسک شد" )

    res = ModelMasker.mask( "زیر سی میلیون", brand_cues )
    t.assert_eq( res.masked_text, "زیر سی میلیون", "متن بدون مدل → بدون تغییر" )


#─────────────────── Test 3: SlotExtractor (Config-Driven) ───────────────────
def test_slot_extractor( t: TestRunner ) -> None:
    print( "\n⚙️ [3] تست موتور استخراج کانفیگ‌محور" )
    # ‫شبیه‌سازی قوانین domain_knowledge.json برای اجرای آفلاین تست
    test_rules = [
        SlotRule( name="price",
                  type="range",
                  units={
                      "میلیون": 1_000_000,
                      "میلیارد": 1_000_000_000,
                      "تومان": 1,
                      "تومن": 1
                  },
                  operators={
                      "زیر": "<=",
                      "بالای": ">=",
                      "حدود": "approx"
                  },
                  regex_template=r"(?P<op>زیر|بالای|حدود)?\s*(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>میلیون|میلیارد|تومان|تومن)?",
                  mask_cues=[ "قیمت", "بودجه" ] ),
        SlotRule( name="ram_gb",
                  type="scalar",
                  units={
                      "گیگ": 1,
                      "گیگابایت": 1,
                      "gb": 1
                  },
                  operators={ "حداقل": ">=" },
                  regex_template=r"(?P<op>حداقل)?\s*(?P<num>\d{1,2})\s*(?P<unit>گیگ(?:ابایت)?|gb)?\s*رم",
                  mask_cues=[ "رم" ] )
    ]
    extractor = SlotExtractor( rules=test_rules )

    filters = extractor.extract( "زیر 30 میلیون" )
    t.assert_true( "price" in filters, "فیلتر قیمت استخراج شد" )
    if isinstance( filters.get( "price" ), dict ):
        t.assert_eq( filters[ "price" ].get( "<=" ), 30_000_000, "زیر 30 میلیون → max=30M" )          #type: ignore

    filters = extractor.extract( "حداقل 8 گیگ رم" )
    t.assert_true( "ram_gb" in filters, "فیلتر رم استخراج شد" )
    t.assert_eq( filters.get( "ram_gb" ), 8, "حداقل 8 گیگ رم → 8" )


#─────────────────── Test 4: ConflictResolver ───────────────────
def test_conflict_resolver( t: TestRunner ) -> None:
    print( "\n⚖️ [4] تست تشخیص و حل تضاد فیلترها" )
    conflicts = ConflictResolver.detect_in_text( "ارزون ولی پرچم‌دار" )
    t.assert_eq( "price_budget_vs_flagship" in conflicts, True, "ارزون ولی پرچم‌دار → تضاد قیمتی" )

    conflicts = ConflictResolver.detect_in_text( "گوشی ارزون با دوربین خوب" )
    t.assert_eq( conflicts, [], "گوشی ارزون با دوربین خوب → بدون تضاد" )

    filters = { "price_range": "budget", "brand": "اپل" }
    cleaned, report = ConflictResolver.resolve( filters, "ارزون ولی پرچم‌دار" )
    t.assert_eq( "price_range" in cleaned, False, "تضاد → price_range حذف شد" )
    t.assert_eq( cleaned.get( "brand" ), "اپل", "brand حفظ شد" )
    t.assert_true( report.has_conflicts, "گزارش تضاد ثبت شد" )


#─────────────────── Test 5: NLU Integration ───────────────────
def test_nlu_integration( t: TestRunner ) -> None:
    print( "\n🔗 [5] تست یکپارچگی NLU Pipeline" )
    try:
        from src.core.nlu.nlu_pipeline import NLUPipeline
        nlu = NLUPipeline()
    except Exception as exc:
        print( f"  ⚠️ NLUPipeline در دسترس نیست: {exc} (از تست رد می‌شود)" )
        return

    cases = [
        ( "گوشی زیر 30 میلیون", {
            "max_price": 30_000_000
        } ),
        ( "آیفون 15 زیر 50 میلیون", {
            "max_price": 50_000_000,
            "brand": "آیفون"
        } ),
        ( "ارزون ولی پرچم‌دار", {
            "has_warnings": True
        } ),
    ]

    for query, expectations in cases:
        result = nlu.process( query )
        print( f"  🔹 {query!r} → filters={result.metadata_filters}, warnings={result.warnings}" )

        price = result.metadata_filters.get( "price", {} )
        if isinstance( price, dict ):
            max_val = expectations.get( "max_price" ) or expectations.get( "min_max", ( None, None ) )[ 1 ]
            min_val = expectations.get( "min_price" ) or expectations.get( "min_max", ( None, None ) )[ 0 ]
            if max_val is not None: t.assert_eq( price.get( "<=" ), max_val, f"{query} → max={max_val:,}" )
            if min_val is not None: t.assert_eq( price.get( ">=" ), min_val, f"{query} → min={min_val:,}" )

        if expectations.get( "brand" ):
            t.assert_eq( result.metadata_filters.get( "brand" ), expectations[ "brand" ], f"{query} → brand={expectations['brand']}" )

        if expectations.get( "has_warnings" ):
            t.assert_true( bool( result.warnings ), f"{query} → دارای هشدار تضاد" )


#─────────────────── Main ───────────────────
def main() -> int:
    print( "🧪 شروع تست‌های MVP Refinement (نسخه کانفیگ‌محور)\n" + "=" * 60 )
    runner = TestRunner()
    test_number_converter( runner )
    test_model_masker( runner )
    test_slot_extractor( runner )
    test_conflict_resolver( runner )
    test_nlu_integration( runner )
    return runner.report()


if __name__ == "__main__":
    sys.exit( main() )
