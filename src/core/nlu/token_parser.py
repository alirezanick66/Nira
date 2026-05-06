"""‫پارسر مبتنی بر توکن (جایگزین Regex)
‫این ماژول مسئول تبدیل متن نرمال‌شده به MetadataFilters است.
‫از الگوی Window-Based Matching، نگاشت‌های کیفی و مدیریت Negation پشتیبانی می‌کند.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, cast

from src.config.domain_loader import ConfigDict
from src.config.logging_config import log_message, LogLevel, LG
from src.core.nlu.number_converter import PersianNumberConverter
from src.core.nlu.schemas import MetadataFilters, MetadataFilterValue, NumericFilterValue

_ConfigSlice: TypeAlias = dict[ str, object ]


@dataclass( frozen=True )
class _Token:
    """نمایش ساختاریافتهٔ یک توکن در جریان پردازش"""
    text: str
    idx: int
    numeric_val: float | None = None


class TokenParser:
    """استخراجگر فیلترها بر اساس جریان توکن‌ها و الگوهای کانفیگ‌محور

    این کلاس کاملاً Stateless طراحی شده و تمام داده‌های دامنه را در زمان
    راه‌اندازی دریافت می‌کند تا وابستگی‌های ضمنی حذف و تست‌پذیری حداکثری شود.
    """

    def __init__( self, domain_config: ConfigDict ) -> None:
        self._slot_defs: dict[ str, _ConfigSlice ] = cast( dict[ str, _ConfigSlice ], domain_config.get( "slot_definitions", {} ) )
        self._negation_kw: frozenset[ str ] = frozenset( cast( list[ str ], domain_config.get( "negation_keywords", [] ) ) )
        self._brands: frozenset[ str ] = frozenset( cast( list[ str ], domain_config.get( "brands", [] ) ) )
        self._colors: frozenset[ str ] = frozenset( cast( list[ str ], domain_config.get( "colors", [] ) ) )
        self._categories: frozenset[ str ] = frozenset( cast( list[ str ], domain_config.get( "categories", [] ) ) )
        self._qual_mappings: dict[ str, dict[ str, str ] ] = cast( dict[ str, dict[ str, str ] ],
                                                                   domain_config.get( "qualitative_mappings", {} ) )
        self._use_case_rules: dict[ str, _ConfigSlice ] = cast( dict[ str, _ConfigSlice ], domain_config.get( "use_case_rules", {} ) )
        self._sep_tokens: frozenset[ str ] = frozenset( cast( list[ str ], domain_config.get( "range_separators", [] ) ) )
        self._brand_norm: dict[ str, str ] = cast( dict[ str, str ], domain_config.get( "brand_normalization", {} ) )

    def parse( self, text: str ) -> MetadataFilters:
        """تبدیل متن نرمال‌شده به MetadataFilters سازگار با Qdrant

        Args:
            text: متن تمیز و نرمال‌شده توسط PersianNormalizer

        Returns:
            دیکشنری فیلترهای استخراج‌شده
        """
        processed_text = self._preprocess_numbers( text )
        tokens = self._tokenize( processed_text )
        filters: MetadataFilters = {}
        consumed_indices: set[ int ] = set()

        self._extract_numeric_slots( tokens, filters, consumed_indices )
        self._extract_enum_slots( tokens, filters, consumed_indices )
        self._apply_contextual_rules( processed_text, filters )

        log_message( LG.NLU, f"✅ پارس توکنی تکمیل | فیلترها: {filters}", LogLevel.DEBUG )
        return filters

    # ─────────────────────────────────────────────────────────────────────────
    # Private Methods
    # ─────────────────────────────────────────────────────────────────────────

    def _preprocess_numbers( self, text: str ) -> str:
        """تبدیل اعداد حروفی به رقمی پیش از توکن‌سازی"""
        words = text.split()
        converted: list[ str ] = []
        for w in words:
            if w in self._negation_kw:
                converted.append( w )
                continue
            num = PersianNumberConverter.convert( w )
            converted.append( str( num ) if num is not None else w )
        return " ".join( converted )

    def _tokenize( self, text: str ) -> list[ _Token ]:
        """ایجاد جریان توکن‌ها + شناسایی مقادیر عددی"""
        tokens: list[ _Token ] = []
        for idx, raw in enumerate( text.split() ):
            try:
                val = float( raw.replace( ",", "." ) )
                tokens.append( _Token( text=raw, idx=idx, numeric_val=val ) )
            except ValueError:
                tokens.append( _Token( text=raw, idx=idx ) )
        return tokens

    def _extract_numeric_slots( self, tokens: list[ _Token ], filters: MetadataFilters, consumed: set[ int ] ) -> None:
        """پیمایش توکن‌ها و مچینگ پنجره‌ای برای اسلات‌های عددی"""
        for i, token in enumerate( tokens ):
            if token.numeric_val is None or i in consumed:
                continue

            for slot_name, cfg in self._slot_defs.items():
                if cfg.get( "type" ) not in ( "range", "scalar" ):
                    continue

                window_size: int = int( cast( int | float, cfg.get( "window", 3 ) ) )

                # ✅ اصلاح: window از قبل از عدد شروع می‌شه تا unit/cue قبل از عدد هم دیده بشه
                start = max( 0, i - window_size )
                end = min( len( tokens ), i + window_size + 1 )
                window_slice = tokens[ start:end ]
                window_texts = { t.text for t in window_slice }

                cues: frozenset[ str ] = frozenset( cast( list[ str ], cfg.get( "cues", [] ) ) )
                units: dict[ str, int | float ] = cast( dict[ str, int | float ], cfg.get( "units", {} ) )
                operators: dict[ str, str ] = cast( dict[ str, str ], cfg.get( "operators", {} ) )

                has_cue = bool( cues & window_texts )
                found_units = [ u for u in window_texts if u in units ]
                found_unit = max( found_units, key=lambda u: units[ u ] ) if found_units else None
                found_op = next( ( o for o in window_texts if o in operators ), None )

                # ✅ اصلاح: تلاش برای رنج قبل از scalar — و در صورت موفقیت، consumed و break درست
                range_val = self._try_match_range( tokens, i, cfg, consumed )
                if range_val is not None:
                    filters[ slot_name ] = range_val
                    log_message( LG.NLU, f"📏 مچ رنج | اسلات: {slot_name} | مقدار: {range_val}", LogLevel.DEBUG )
                    break          # این توکن مصرف شد، slot بعدی رو چک نکن

                is_match = has_cue or bool( found_unit )
                if not is_match:
                    continue

                multiplier = units.get( found_unit, 1 ) if found_unit else 1
                final_val = token.numeric_val * multiplier
                op = operators[ found_op ] if found_op else ( ">=" if cfg.get( "type" ) == "scalar" else "<=" )

                filters[ slot_name ] = cast( NumericFilterValue, { op: final_val } )
                consumed.add( i )
                for t in window_slice:
                    if t.text in operators or t.text in units or t.text in cues:
                        consumed.add( t.idx )

                log_message( LG.NLU, f"🔢 مچ عددی | اسلات: {slot_name} | مقدار: {final_val} | عملگر: {op}", LogLevel.DEBUG )
                break          # این توکن برای این slot مصرف شد

    def _extract_enum_slots( self, tokens: list[ _Token ], filters: MetadataFilters, consumed: set[ int ] ) -> None:
        """تشخیص مقادیر ثابت + مدیریت Negation"""
        enum_defs = {
            "brand": ( self._brands, "brand" ),
            "color": ( self._colors, "color" ),
            "category": ( self._categories, "category" ),
        }

        for t in tokens:
            if t.idx in consumed:
                continue

            is_neg = any( tokens[ j ].text in self._negation_kw for j in range( max( 0, t.idx - 2 ), t.idx ) )
            val_lower = t.text.lower()

            for slot_key, ( vocab, target_key ) in enum_defs.items():
                if val_lower not in vocab:
                    continue

                dest_key = f"{target_key}_not" if is_neg else target_key
                canonical_val = self._brand_norm.get( t.text, t.text ) if slot_key == "brand" else t.text
                current = filters.get( dest_key )

                if current is None:
                    filters[ dest_key ] = canonical_val
                elif isinstance( current, list ):
                    if canonical_val not in current:
                        current.append( canonical_val )
                else:
                    filters[ dest_key ] = [ str( current ), canonical_val ]

                consumed.add( t.idx )
                log_message( LG.NLU, f"🏷️ مچ Enum | کلید: {dest_key} | مقدار: {t.text}", LogLevel.DEBUG )
                break

    def _apply_contextual_rules( self, text: str, filters: MetadataFilters ) -> None:
        """اعمال نگاشت‌های کیفی و قواعد استفاده بر اساس حضور کلمه یا عبارت"""
        words = set( text.split() )

        # ── نگاشت کیفی ───────────────────────────────────────────────────────
        for phrase, mapping in self._qual_mappings.items():
            # ✅ یک حلقه واحد: کلمات تکی با `in words`، چندکلمه‌ای با `in text`
            matched = ( phrase in words ) if " " not in phrase else ( phrase in text )
            if not matched:
                continue
            for key, val in mapping.items():
                self._apply_single_mapping( filters, key, val )
            log_message( LG.NLU, f"🎨 مچ کیفی | عبارت: {phrase} → {mapping}", LogLevel.DEBUG )

        # ── قواعد استفاده ─────────────────────────────────────────────────────
        for trigger, rule in self._use_case_rules.items():
            if trigger not in text:
                continue
            for key, val in rule.items():
                if key == "tags":
                    tags = filters.setdefault( "tags", [] )
                    if isinstance( tags, list ):
                        tags.extend( [ t for t in cast( list[ str ], val ) if t not in tags ] )
                elif isinstance( val, dict ):
                    _OP_MAP = { "gte": ">=", "lte": "<=", "gt": ">", "lt": "<" }
                    for op_alias, op_val in val.items():
                        qdrant_op = cast( str, _OP_MAP.get( op_alias, op_alias ) )
                        current = filters.get( key )
                        if isinstance( current, dict ):
                            cast( dict[ str, object ], current )[ qdrant_op ] = op_val
                        else:
                            filters[ key ] = cast( NumericFilterValue, { qdrant_op: op_val } )
                else:
                    filters[ key ] = cast( MetadataFilterValue, val )
            log_message( LG.NLU, f"🎯 اعمال Use-Case | Trigger: {trigger}", LogLevel.DEBUG )

    @staticmethod
    def _apply_single_mapping( filters: MetadataFilters, key: str, val: object ) -> None:
        """‫اعمال یک نگاشت کیفی روی فیلترها با جلوگیری از override فیلتر عددی"""
        current = filters.get( key )
        if isinstance( current, dict ) and not isinstance( val, dict ):
            log_message( LG.NLU, f"⛔ نادیده‌گرفتن نگاشت کیفی روی فیلتر عددی {key}", LogLevel.WARNING )
            return
        if current is None:
            filters[ key ] = cast( MetadataFilterValue, val )
        elif isinstance( current, dict ):
            cast( dict[ str, object ], current ).update( val if isinstance( val, dict ) else { key: val } )

    def _try_match_range( self, tokens: list[ _Token ], start_idx: int, cfg: _ConfigSlice,
                          consumed: set[ int ] ) -> NumericFilterValue | None:
        """شناسایی الگوی رنج عددی (مثلاً: ۱۰ تا ۲۰ میلیون)"""
        num1 = tokens[ start_idx ].numeric_val
        if num1 is None:
            return None

        units = cast( dict[ str, float ], cfg.get( "units", {} ) )
        window_size: int = int( cast( int | float, cfg.get( "window", 3 ) ) )
        window_limit = min( len( tokens ), start_idx + 5 )

        for j in range( start_idx + 1, window_limit ):
            if tokens[ j ].text not in self._sep_tokens:
                continue

            for k in range( j + 1, min( len( tokens ), j + 3 ) ):
                num2 = tokens[ k ].numeric_val
                if num2 is None or k in consumed:
                    continue

                min_v, max_v = sorted( ( num1, num2 ) )

                # ✅ اصلاح: window از قبل از عدد اول شروع می‌شه تا unit قبل از عدد دیده بشه
                search_start = max( 0, start_idx - window_size )
                search_end = min( len( tokens ), k + window_size + 1 )
                combined_texts = { t.text for t in tokens[ search_start:search_end ] }

                found_unit = next( ( u for u in combined_texts if u in units ), None )
                multiplier = units[ found_unit ] if found_unit else 1.0

                consumed.update( [ start_idx, j, k ] )
                return cast( NumericFilterValue, { ">=": min_v * multiplier, "<=": max_v * multiplier } )

        return None
