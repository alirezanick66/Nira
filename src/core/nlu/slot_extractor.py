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
            scaled_value = value * rule.units.get( unit.lower(), rule.default_unit_multiplier )

            if rule.type == "range":
                if op in { "<=", "<" }:
                    filters[ rule.name ] = { op: scaled_value }
                elif op in { ">=", ">" }:
                    filters[ rule.name ] = { op: scaled_value }
                elif op == "approx":
                    margin = int( scaled_value * 0.1 )
                    filters[ rule.name ] = { ">=": scaled_value - margin, "<=": scaled_value + margin }
            else:
                filters[ rule.name ] = scaled_value

            log_message( LG.NLU, f"اسلات {rule.name} استخراج شد: {value} {unit}", LogLevel.DEBUG )
        return filters

    def _parse_groups( self, match: re.Match[ str ], rule: SlotRule ) -> tuple[ float | None, str, str ]:
        """‫استخراج و نرمال‌سازی مقادیر از گروه‌های رگکس‫"""
        # ✅ رفع باگ: حذف فاصلهٔ اضافی از کلیدهای دیکشنری
        num_str = ( match.groupdict().get( "num" ) or match.groupdict().get( "amount" ) or "" ).strip()
        unit = ( match.groupdict().get( "unit" ) or "" ).lower()
        op = ( match.groupdict().get( "op" ) or "" ).lower()

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
