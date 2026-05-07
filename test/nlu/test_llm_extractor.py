"""تست سبک برای LLMNLUExtractor با LLM شبیه‌سازی‌شده"""
from __future__ import annotations

import asyncio

from src.core.llm.memory import ConversationMemory
from src.core.nlu.llm_extractor import LLMNLUExtractor, _DEFAULT_GREETING
from src.core.nlu.normalizer import PersianNormalizer
from src.config.domain_loader import DomainConfigLoader


class _TestRunner:
    def __init__( self ) -> None:
        self.passed = 0
        self.failed = 0

    def assert_true( self, cond: bool, msg: str ) -> None:
        if cond:
            print( f"✅ {msg}" )
            self.passed += 1
        else:
            print( f"❌ {msg}" )
            self.failed += 1

    def assert_eq( self, actual: object, expected: object, msg: str ) -> None:
        self.assert_true( actual == expected, f"{msg} | expected={expected!r}, got={actual!r}" )

    def report( self ) -> int:
        print( f"📊 {self.passed} passed | {self.failed} failed" )
        return 0 if self.failed == 0 else 1


class DummyExtractor( LLMNLUExtractor ):
    """نسخه تستی برای کنترل خروجی LLM بدون وابستگی شبکه"""

    def __init__( self, memory: ConversationMemory | None = None ) -> None:
        loader = DomainConfigLoader()
        self._config = loader.load( "mobile" )
        self._normalizer = PersianNormalizer()
        self._memory = memory or ConversationMemory()
        self._greeting_responses = [ _DEFAULT_GREETING ]
        self._next_response = ""
        self.last_messages: list[ dict[ str, str ] ] = []

    def set_response( self, text: str ) -> None:
        self._next_response = text

    async def _call_llm( self, messages ):  # type: ignore[override]
        self.last_messages = messages
        return self._next_response


def test_history_injected( runner: _TestRunner ) -> None:
    memory = ConversationMemory()
    session_id = "sess-history"
    asyncio.run( memory.add_message( session_id, "user", "گوشی زیر ۳۰ میلیون" ) )
    extractor = DummyExtractor( memory=memory )
    extractor.set_response(
        '{"intent":"refine","semantic_query":"سامسونگ","metadata_filters":{"brand":"سامسونگ"},'
        '"is_greeting":false,"sort_directive":null}'
    )
    result = asyncio.run( extractor.extract( "سامسونگ باشه", session_id ) )
    runner.assert_eq( result.intent, "refine", "Intent باید refine باشد" )
    runner.assert_true(
        any( msg.get( "content" ) == "گوشی زیر ۳۰ میلیون" for msg in extractor.last_messages ),
        "تاریخچه مکالمه باید در پیام‌های LLM حضور داشته باشد",
    )


def test_number_conversion( runner: _TestRunner ) -> None:
    extractor = DummyExtractor()
    extractor.set_response(
        '{"intent":"search","semantic_query":"گوشی","metadata_filters":{"price":{"<=":"20000000"}},'
        '"is_greeting":false,"sort_directive":null}'
    )
    asyncio.run( extractor.extract( "گوشی زیر سی میلیون", "sess-num" ) )
    last_user = extractor.last_messages[ -1 ].get( "content", "" )
    runner.assert_true( "30000000" in last_user, "اعداد حروفی باید قبل از LLM به عدد تبدیل شوند" )


def test_numeric_filter_parsing( runner: _TestRunner ) -> None:
    extractor = DummyExtractor()
    extractor.set_response(
        '{"intent":"search","semantic_query":"گوشی","metadata_filters":{"price":{"<=":"20000000"}},'
        '"is_greeting":false,"sort_directive":null}'
    )
    result = asyncio.run( extractor.extract( "گوشی زیر ۲۰ میلیون", "sess-price" ) )
    price = result.metadata_filters.get( "price", {} )
    runner.assert_eq( price.get( "<=" ), 20000000.0, "قیمت رشته‌ای باید به float تبدیل شود" )


def test_json_error_fallback( runner: _TestRunner ) -> None:
    extractor = DummyExtractor()
    extractor.set_response( "not-json" )
    result = asyncio.run( extractor.extract( "گوشی", "sess-error" ) )
    runner.assert_eq( result.intent, "search", "در صورت خطا intent باید search باشد" )
    runner.assert_true( bool( result.warnings ), "در صورت خطا باید warning ثبت شود" )


def test_empty_input( runner: _TestRunner ) -> None:
    extractor = DummyExtractor()
    extractor.set_response(
        '{"intent":"greeting","semantic_query":"","metadata_filters":{},'
        '"is_greeting":true,"sort_directive":null}'
    )
    result = asyncio.run( extractor.extract( "", "sess-empty" ) )
    runner.assert_true( result.is_greeting, "ورودی خالی باید خروجی معتبر تولید کند" )


def main() -> int:
    runner = _TestRunner()
    test_history_injected( runner )
    test_number_conversion( runner )
    test_numeric_filter_parsing( runner )
    test_json_error_fallback( runner )
    test_empty_input( runner )
    return runner.report()


if __name__ == "__main__":
    raise SystemExit( main() )
