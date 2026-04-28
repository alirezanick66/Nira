"""‫استخراجگر کانفیگ‌محور اسلات‌های عددی و مقداری‫"""
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.schemas import MetadataFilters
from src.core.nlu.number_converter import PersianNumberConverter
from src.core.nlu.model_masker import ModelMasker


class SlotRule( BaseModel ):
    """‫تعریف یک اسلات استخراج‌پذیر‫"""
    name: str
    type: Literal[ "range", "scalar", "enum" ]
    units: dict[ str, int | float ] = Field( default_factory=dict )
    operators: dict[ str, str ] = Field( default_factory=dict )
    regex_template: str
    mask_cues: list[ str ] = Field( default_factory=list )
    default_unit_multiplier: int | float = 1


class SlotExtractor:
    """‫موتور سبک استخراج اسلات بر اساس کانفیگ دامنه‫"""

    def __init__( self, rules: list[ SlotRule ] ) -> None:
        self._rules = rules
        self._compiled_patterns: dict[ str, re.Pattern[ str ] ] = {}
        for rule in rules:
            try:
                self._compiled_patterns[ rule.name ] = re.compile( rule.regex_template, re.IGNORECASE )
            except re.error as exc:
                log_message( LG.NLU, f"خطای کامپایل رگکس برای {rule.name}: {exc}", LogLevel.WARNING )

    def extract( self, text: str ) -> MetadataFilters:
        """‫اجرای چرخهٔ استخراج روی متن نرمال‌شده‫"""
        filters: MetadataFilters = {}
        for rule in self._rules:
            pattern = self._compiled_patterns.get( rule.name )
            if not pattern:
                continue

            cues = frozenset( rule.mask_cues )
            mask_res = ModelMasker.mask( text, cues )
            matched = pattern.search( mask_res.masked_text )
            if not matched:
                continue

            value, unit, op = self._parse_groups( matched, rule )
            if value is None:
                continue

            #‫تبدیل واحد و اعمال عملگر
            if isinstance( value, dict ) and op == "range":
                # حالت range
                filters[ rule.name ] = { ">=": value[ "min" ], "<=": value[ "max" ] }
            elif rule.type == "range" and isinstance( value, ( int, float ) ):
                scaled_value = value * rule.units.get( unit.lower(), rule.default_unit_multiplier )
                if op in { "<=", "<" }:
                    filters[ rule.name ] = { op: scaled_value }
                elif op in { ">=", ">" }:
                    filters[ rule.name ] = { op: scaled_value }
                elif op == "approx":
                    margin = int( scaled_value * 0.1 )
                    filters[ rule.name ] = { ">=": scaled_value - margin, "<=": scaled_value + margin }
            elif isinstance( value, ( int, float ) ):
                filters[ rule.name ] = value

            log_message( LG.NLU, f"اسلات {rule.name} استخراج شد: {value} {unit}", LogLevel.DEBUG )
        return filters

    def _parse_groups( self, match: re.Match[ str ],
                       rule: SlotRule ) -> tuple[ float | None, str, str ] | tuple[ dict[ str, float ], str, str ]:
        """‫استخراج و نرمال‌سازی مقادیر از گروه‌های رگکس‫"""
        num_str = ( match.groupdict().get( "num1" ) or match.groupdict().get( "num2" ) or match.groupdict().get( "num" )
                    or match.groupdict().get( "amount" ) or "" ).strip()
        unit = ( match.groupdict().get( "unit" ) or "" ).lower()
        op = ( match.groupdict().get( "op" ) or "" ).lower()

        # ✅ پشتیبانی از range "بین X تا Y"
        min_str = ( match.groupdict().get( "min" ) or "" ).strip()
        max_str = ( match.groupdict().get( "max" ) or "" ).strip()
        range_unit = ( match.groupdict().get( "range_unit" ) or match.groupdict().get( "unit" ) or "" ).lower()

        # ── حالت ۱: range (min/max present) ──
        if min_str and max_str:
            try:
                min_val = float( min_str.replace( ",", "." ) )
                max_val = float( max_str.replace( ",", "." ) )
            except ( ValueError, TypeError ):
                return None, range_unit, ""

            # نگاشت عملگر خالی برای range
            multiplier = rule.units.get( range_unit, rule.default_unit_multiplier )
            return { "min": min_val * multiplier, "max": max_val * multiplier }, range_unit, "range"

        # ── حالت ۲: single value ──
        if not num_str:
            return None, unit, op

        # ✅ فیلتر FP: اعداد کوچک ambiguous بدون unit قیمتی
        _AMBIGUOUS_NUMBERS = frozenset( { "یه", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه" } )
        if rule.name == "price" and num_str in _AMBIGUOUS_NUMBERS and not unit:
            return None, unit, op

        #‫پشتیبانی از اعداد حروفی
        num_value = PersianNumberConverter.convert( num_str )
        if num_value is None:
            try:
                num_value = float( num_str.replace( ",", "." ) )
            except ( ValueError, TypeError ):
                return None, unit, op

        #‫نگاشت عملگرهای محاوره‌ای
        op_map = { "زیر": "<=", "کمتر": "<=", "بالای": ">=", "بیشتر": ">=", "حدود": "approx" }
        normalized_op = op_map.get( op, op )
        return num_value, unit, normalized_op
