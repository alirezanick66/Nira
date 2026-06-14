"""‫تست منطق انتخاب محصولات نمایش بر اساس product_ids منتخب LLM

‫هدف: اطمینان از اینکه results نهایی دقیقاً همان محصولاتی است که LLM انتخاب کرده،
‫با حفظ ترتیب و گاردهای ایمن (fail-safe) برای ورودی‌های نامعتبر/خالی.

‫این تست سبک است و وابستگی سنگین (Qdrant/Groq) را لود نمی‌کند؛ بنابراین
‫تابع واقعی را با تزریق stub برای log_message ایزوله اجرا می‌کنیم.
"""
from __future__ import annotations
import sys
import types
from dataclasses import dataclass


# ── ساخت stub سبک برای logging_config تا از زنجیره import سنگین جلوگیری شود ──
def _install_logging_stub() -> None:
    if "src.config.logging_config" in sys.modules:
        return
    stub = types.ModuleType( "src.config.logging_config" )

    def _noop( *args, **kwargs ):
        return None

    class _LG:
        LLM = "LLM"
        API = "API"
        RETRIEVAL = "RETRIEVAL"

    class _LogLevel:
        DEBUG = "DEBUG"
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"

    stub.log_message = _noop
    stub.LG = _LG
    stub.LogLevel = _LogLevel
    sys.modules[ "src.config.logging_config" ] = stub


# ── مدل ساده محصول که فقط product_id مهم است (سازگار با امضای متد) ──
@dataclass
class _FakeProduct:
    product_id: int


def _load_select_fn():
    """‫بارگذاری ایزولهٔ تابع _select_llm_products از سورس واقعی بدون importهای سنگین."""
    _install_logging_stub()
    import importlib.util
    import pathlib
    import textwrap

    src = pathlib.Path( __file__ ).resolve().parents[ 1 ] / "src" / "services" / "search_service.py"
    text = src.read_text( encoding="utf-8" )

    # استخراج بدنهٔ متد _select_llm_products به‌صورت یک تابع مستقل (همان منطق دقیق)
    marker = "    @staticmethod\n    def _select_llm_products("
    start = text.index( marker )
    end = text.index( "\n    def _build_final_response(", start )
    block = text[ start:end ]

    # حذف دکوراتور و dedent
    block = block.replace( "    @staticmethod\n", "", 1 )
    block = textwrap.dedent( block )

    ns: dict = {}
    from src.config.logging_config import log_message, LG, LogLevel  # type: ignore
    ns.update( { "log_message": log_message, "LG": LG, "LogLevel": LogLevel } )
    exec( compile( block, str( src ), "exec" ), ns )
    return ns[ "_select_llm_products" ]


select = _load_select_fn()


def test_single_id_returns_only_that_product():
    """‫اگر LLM یک محصول انتخاب کند، فقط همان یکی برگردد (سناریوی اصلی باگ)."""
    products = [ _FakeProduct( 9422534 ), _FakeProduct( 531999 ) ]
    out = select( products, { "product_ids": [ 9422534 ] } )
    assert [ p.product_id for p in out ] == [ 9422534 ]


def test_order_follows_llm_choice():
    """‫ترتیب خروجی باید از انتخاب LLM پیروی کند، نه ترتیب rerank."""
    products = [ _FakeProduct( 100 ), _FakeProduct( 200 ) ]
    out = select( products, { "product_ids": [ 200, 100 ] } )
    assert [ p.product_id for p in out ] == [ 200, 100 ]


def test_empty_ids_falls_back_to_all():
    """‫لیست خالی → بازگشت ایمن به همهٔ محصولات."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [] } )
    assert [ p.product_id for p in out ] == [ 1, 2 ]


def test_missing_key_falls_back_to_all():
    """‫نبود کلید product_ids → بازگشت ایمن به همهٔ محصولات."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, {} )
    assert [ p.product_id for p in out ] == [ 1, 2 ]


def test_no_match_falls_back_to_all():
    """‫اگر هیچ id منتخب با محصولات منطبق نشد → بازگشت ایمن به همهٔ محصولات."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [ 999 ] } )
    assert [ p.product_id for p in out ] == [ 1, 2 ]


def test_partial_match_keeps_only_valid():
    """‫idهای منتخب که بعضی منطبق و بعضی نامعتبرند → فقط منطبق‌ها."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [ 2, 999 ] } )
    assert [ p.product_id for p in out ] == [ 2 ]


def test_string_ids_are_normalized():
    """‫شناسه‌های رشته‌ای (خروجی احتمالی LLM) باید به int نرمال شوند."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [ "2" ] } )
    assert [ p.product_id for p in out ] == [ 2 ]


def test_duplicate_ids_deduped_preserving_order():
    """‫idهای تکراری حذف شوند ولی ترتیب اولین ظهور حفظ شود."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [ 2, 2, 1 ] } )
    assert [ p.product_id for p in out ] == [ 2, 1 ]


def test_invalid_id_types_ignored():
    """‫مقادیر نامعتبر (None/dict) نادیده گرفته شوند، بقیه پردازش شوند."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": [ None, { "x": 1 }, 1 ] } )
    assert [ p.product_id for p in out ] == [ 1 ]


def test_non_list_product_ids_falls_back():
    """‫اگر product_ids از نوع list نباشد → بازگشت ایمن به همه."""
    products = [ _FakeProduct( 1 ), _FakeProduct( 2 ) ]
    out = select( products, { "product_ids": "9422534" } )
    assert [ p.product_id for p in out ] == [ 1, 2 ]


if __name__ == "__main__":
    fns = [ v for k, v in sorted( globals().items() ) if k.startswith( "test_" ) and callable( v ) ]
    passed = 0
    for fn in fns:
        fn()
        print( f"✅ {fn.__name__}" )
        passed += 1
    print( f"\n{passed}/{len(fns)} تست با موفقیت گذشت" )
