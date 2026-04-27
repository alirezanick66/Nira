"""‫ماسک کردن هوشمند شماره مدل‌ها برای جلوگیری از تداخل با استخراج مقدار‫"""
import re
from dataclasses import dataclass, field
from src.config.logging_config import log_message, LogLevel, LG


@dataclass( frozen=True )
class MaskResult:
    """‫نتیجهٔ ماسک‌کردن متن ورودی‫"""
    masked_text: str
    placeholders: dict[ str, str ] = field( default_factory=dict )


class ModelMasker:
    """‫شناساگر و ماسک‌کنندهٔ شماره مدل بر اساس کلمات کلیدی دامنه‫"""

    _MODEL_PREFIX_PATTERN: str = r"(?:{keywords})\s*"
    _INLINE_PATTERN: re.Pattern[ str ] = re.compile( r"\b([A-Za-z]{1,5})(\d{1,2})\b" )
    _PLACEHOLDER_TEMPLATE: str = "__MODEL_{idx}__"

    @classmethod
    def mask( cls, text: str, brand_cues: frozenset[ str ] | None = None ) -> MaskResult:
        """‫جایگزینی شماره مدل‌ها با placeholder ایمن‫"""
        if brand_cues is None:
            return MaskResult( masked_text=text )

        masked = text
        placeholders: dict[ str, str ] = {}
        idx = 0

        #‫الگوی ۱: کلمهٔ کلیدی برند + عدد جداگانه
        keywords_regex = "|".join( re.escape( kw ) for kw in brand_cues )
        prefix_pat = re.compile( cls._MODEL_PREFIX_PATTERN.format( keywords=keywords_regex ), re.IGNORECASE )

        def _replace_prefix( match: re.Match[ str ] ) -> str:
            nonlocal idx
            matched_group = match.group( 0 ).strip()
            #‫جستجوی عدد پس از کلمهٔ کلیدی
            number_match = re.search( r"\d{1,2}", text[ match.end():match.end() + 5 ] )
            if number_match:
                original = f"{matched_group} {number_match.group(0)}"
                placeholder = cls._PLACEHOLDER_TEMPLATE.format( idx=idx )
                placeholders[ placeholder ] = original
                idx += 1
                return f"{matched_group} {placeholder}"
            return matched_group

        masked = prefix_pat.sub( _replace_prefix, masked )

        #‫الگوی ۲: ترکیب حرف+عدد چسبیده (S24, A52, Note13)
        for inline_match in cls._INLINE_PATTERN.finditer( masked ):
            prefix = inline_match.group( 1 ).lower()
            if any( prefix.startswith( cue[ :3 ].lower() )
                    for cue in brand_cues ) or prefix in { "s", "a", "p", "se", "note", "redmi" }:
                original = inline_match.group( 0 )
                placeholder = cls._PLACEHOLDER_TEMPLATE.format( idx=idx )
                placeholders[ placeholder ] = original
                idx += 1
                masked = masked.replace( original, inline_match.group( 1 ) + placeholder, 1 )

        log_message( LG.NLU, f"ماسک مدل: {len(placeholders)} مورد شناسایی شد", LogLevel.DEBUG )
        return MaskResult( masked_text=masked, placeholders=placeholders )
