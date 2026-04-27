"""‫تست واحد فیچرهای فاز MVP Refinement

‫پوشش:
1. ✅ UnitParser: اعداد حرفی، بازه‌ها، اعداد مدل
2. ✅ ConflictResolver: تشخیص تضاد در فیلترها
3. ✅ NLUPipeline: یکپارچگی دو ماژول جدید

‫نکته: این تست‌ها نیازی به Qdrant/PostgreSQL ندارند و کاملاً آفلاین اجرا می‌شوند.

‫نحوه اجرا:
    uv run python scripts/nlu/test_mvp_refinement.py
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import sys
from typing import Any

#───────────────────── Local Imports ─────────────────────
from src.core.nlu.unit_parser import UnitParser, PriceFilter, UnitValue
from src.core.nlu.conflict_resolver import ConflictResolver

# ‫NLUPipeline به KnowledgeCache نیاز دارد - فقط در تست یکپارچه import می‌شود


# ─────────────────── Helper ───────────────────
class TestRunner:

    def __init__( self ) -> None:
        self.passed = 0
        self.failed = 0
        self.failures: list[ str ] = []

    def assert_eq( self, actual: Any, expected: Any, msg: str ) -> None:
        if actual == expected:
            self.passed += 1
            print( f"  ✅ {msg}" )
        else:
            self.failed += 1
            err = f"{msg} | expected={expected!r}, got={actual!r}"
            self.failures.append( err )
            print( f"  ❌ {err}" )

    def assert_true( self, cond: bool, msg: str ) -> None:
        self.assert_eq( bool( cond ), True, msg )

    def assert_in_range( self, actual: int | None, low: int, high: int, msg: str ) -> None:
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


#─────────────────── Test: UnitParser ───────────────────
def test_word_numbers( t: TestRunner ) -> None:
    print( "\n🔢 [1] تست تبدیل اعداد حرفی فارسی" )
    t.assert_eq( UnitParser.parse_word_number( "سی" ), 30, "سی → 30" )
    t.assert_eq( UnitParser.parse_word_number( "چهل و پنج" ), 45, "چهل و پنج → 45" )
    t.assert_eq( UnitParser.parse_word_number( "صد" ), 100, "صد → 100" )
    t.assert_eq( UnitParser.parse_word_number( "بیست" ), 20, "بیست → 20" )
    t.assert_eq( UnitParser.parse_word_number( "" ), None, "خالی → None" )
    t.assert_eq( UnitParser.parse_word_number( "هیچ" ), None, "غیرعدد → None" )


def test_price_filter( t: TestRunner ) -> None:
    print( "\n💰 [2] تست استخراج قیمت" )

    # ‫زیر X میلیون
    pf = UnitParser.extract_price_filter( "گوشی زیر 30 میلیون" )
    t.assert_eq( pf.max_value, 30_000_000, "زیر 30 میلیون → max=30M" )
    t.assert_eq( pf.min_value, None, "زیر 30 میلیون → بدون min" )

    # ‫بالای X میلیون
    pf = UnitParser.extract_price_filter( "بالای 20 میلیون تومان" )
    t.assert_eq( pf.min_value, 20_000_000, "بالای 20 میلیون → min=20M" )

    # ‫سی میلیون (عدد حرفی)
    pf = UnitParser.extract_price_filter( "زیر سی میلیون" )
    t.assert_eq( pf.max_value, 30_000_000, "زیر سی میلیون → max=30M" )

    # ‫حدود X (بازه ±15٪)
    pf = UnitParser.extract_price_filter( "حدود 40 میلیون" )
    t.assert_in_range( pf.max_value, 45_000_000, 47_000_000, "حدود 40 میلیون → max≈46M" )
    t.assert_in_range( pf.min_value, 33_000_000, 35_000_000, "حدود 40 میلیون → min≈34M" )

    # ‫بازه: 30 تا 50 میلیون
    pf = UnitParser.extract_price_filter( "بین 30 تا 50 میلیون" )
    t.assert_eq( pf.min_value, 30_000_000, "30 تا 50 میلیون → min=30M" )
    t.assert_eq( pf.max_value, 50_000_000, "30 تا 50 میلیون → max=50M" )

    # ‫بازه با خط فاصله
    pf = UnitParser.extract_price_filter( "40-50 میلیون" )
    t.assert_eq( pf.min_value, 40_000_000, "40-50 میلیون → min=40M" )
    t.assert_eq( pf.max_value, 50_000_000, "40-50 میلیون → max=50M" )


def test_model_number_protection( t: TestRunner ) -> None:
    print( "\n📱 [3] تست محافظت از اعداد مدل (آیفون 15، S24)" )

    # ‫«آیفون 15 ارزون» نباید 15 رو به‌عنوان قیمت استخراج کنه
    pf = UnitParser.extract_price_filter( "آیفون 15 ارزون میخوام" )
    t.assert_eq( pf.is_empty, True, "آیفون 15 → بدون قیمت" )

    # ‫«آیفون 15 زیر 50 میلیون» باید 50 رو استخراج کنه نه 15
    pf = UnitParser.extract_price_filter( "آیفون 15 زیر 50 میلیون" )
    t.assert_eq( pf.max_value, 50_000_000, "آیفون 15 زیر 50 میلیون → max=50M" )

    # ‫«S24» (حرف+عدد چسبیده) نباید قیمت استخراج کنه
    pf = UnitParser.extract_price_filter( "گلکسی S24 خوبه؟" )
    t.assert_eq( pf.is_empty, True, "S24 → بدون قیمت" )

    # ‫«Note 13 زیر 20 میلیون»
    pf = UnitParser.extract_price_filter( "Note 13 زیر 20 میلیون" )
    t.assert_eq( pf.max_value, 20_000_000, "Note 13 زیر 20 میلیون → max=20M" )


def test_memory_filter( t: TestRunner ) -> None:
    print( "\n💾 [4] تست استخراج رم و حافظه" )

    ram = UnitParser.extract_memory_filter( "رم 8 گیگ", key="ram" )
    t.assert_true( ram is not None, "رم 8 گیگ → یافت شد" )
    if ram:
        t.assert_eq( ram.value, 8, "رم 8 گیگ → 8" )
        t.assert_eq( ram.unit, "GB", "رم 8 گیگ → GB" )

    ram = UnitParser.extract_memory_filter( "8 گیگابایت رم", key="ram" )
    if ram:
        t.assert_eq( ram.value, 8, "8 گیگابایت رم → 8" )
        t.assert_eq( ram.unit, "GB", "8 گیگابایت رم → GB" )

    storage = UnitParser.extract_memory_filter( "حافظه 256 گیگ", key="storage" )
    if storage:
        t.assert_eq( storage.value, 256, "حافظه 256 گیگ → 256" )
        t.assert_eq( storage.unit, "GB", "حافظه 256 گیگ → GB" )


#─────────────────── Test: ConflictResolver ───────────────────
def test_conflict_resolver( t: TestRunner ) -> None:
    print( "\n⚔️  [5] تست تشخیص تضاد فیلترها" )

    # ‫متن تضاد
    conflicts = ConflictResolver.detect_in_text( "ارزون ولی پرچم‌دار" )
    t.assert_eq( "price_budget_vs_flagship" in conflicts, True, "ارزون ولی پرچم‌دار → تضاد قیمتی" )

    # ‫بدون تضاد
    conflicts = ConflictResolver.detect_in_text( "گوشی ارزون با دوربین خوب" )
    t.assert_eq( conflicts, [], "گوشی ارزون با دوربین خوب → بدون تضاد" )

    # ‫حل تضاد در فیلترها
    filters = { "price_range": "budget", "brand": "اپل" }
    cleaned, report = ConflictResolver.resolve( filters, "ارزون ولی پرچم‌دار" )
    t.assert_eq( "price_range" in cleaned, False, "تضاد ارزون+پرچم‌دار → price_range حذف شد" )
    t.assert_eq( cleaned[ "brand" ], "اپل", "brand حفظ شد" )
    t.assert_true( report.has_conflicts, "گزارش تضاد ثبت شد" )


#─────────────────── Test: Integration with NLU ───────────────────
def test_nlu_integration( t: TestRunner ) -> None:
    print( "\n🔗 [6] تست یکپارچگی NLU Pipeline (نیاز به KnowledgeCache)" )

    try:
        from src.core.nlu.nlu_pipeline import NLUPipeline
        nlu = NLUPipeline()
    except Exception as exc:
        print( f"  ⚠️ NLUPipeline در دسترس نیست: {exc} (از تست رد می‌شود)" )
        return

    cases = [
        ( "گوشی زیر سی میلیون", { "min_max": ( None, 30_000_000 ) } ),
        # ‫نکته: «آیفون» در domain_knowledge.json به‌عنوان برند جدا از «اپل» ثبت شده است
        ( "آیفون 15 زیر 50 میلیون", { "min_max": ( None, 50_000_000 ), "brand": "آیفون" } ),
        ( "بین 30 تا 50 میلیون", { "min_max": ( 30_000_000, 50_000_000 ) } ),
        ( "ارزون ولی پرچم‌دار", { "warnings_present": True } ),
    ]

    for query, expectations in cases:
        result = nlu.process( query )
        print( f"  🔹 {query!r} → filters={result.metadata_filters}, warnings={result.warnings}" )

        if "min_max" in expectations:
            min_exp, max_exp = expectations[ "min_max" ]
            price = result.metadata_filters.get( "price", {} )
            if isinstance( price, dict ):
                if max_exp is not None:
                    t.assert_eq( price.get( "<" ), max_exp, f"{query} → max={max_exp:,}" )
                if min_exp is not None:
                    t.assert_eq( price.get( ">=" ), min_exp, f"{query} → min={min_exp:,}" )

        if expectations.get( "brand" ):
            t.assert_eq( result.metadata_filters.get( "brand" ), expectations[ "brand" ],
                         f"{query} → brand={expectations['brand']}" )

        if expectations.get( "warnings_present" ):
            t.assert_true( bool( result.warnings ), f"{query} → دارای هشدار" )


#─────────────────── Main ───────────────────
def main() -> int:
    print( "🧪 شروع تست‌های MVP Refinement\n" + "=" * 60 )

    runner = TestRunner()
    test_word_numbers( runner )
    test_price_filter( runner )
    test_model_number_protection( runner )
    test_memory_filter( runner )
    test_conflict_resolver( runner )
    test_nlu_integration( runner )

    return runner.report()


if __name__ == "__main__":
    sys.exit( main() )
