"""‫ماسک کردن هوشمند شماره مدل‌ها برای جلوگیری از تداخل با استخراج مقدار‫"""
import re
from dataclasses import dataclass, field
from src.config.logging_config import log_message, LogLevel, LG

_RTL = "\u200F"


@dataclass( frozen=True )
class MaskResult:
    """‫نتیجهٔ ماسک‌کردن متن ورودی‫"""
    masked_text: str
    placeholders: dict[ str, str ] = field( default_factory=dict )


class ModelMasker:
    """‫شناساگر و ماسک‌کنندهٔ شماره مدل بر اساس کلمات کلیدی دامنه‫"""
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

        # ✅ الگوی ۱: کلمهٔ کلیدی برند + عدد (بدون اجبار فاصلهٔ پسین)
        keywords_regex = "|".join( re.escape( kw ) for kw in brand_cues )
        prefix_pat = re.compile( rf"\b(?:{keywords_regex})\s*(\d{{1,2}})\b", re.IGNORECASE )

        def _replace_prefix( match: re.Match[ str ] ) -> str:
            nonlocal idx
            full_match = match.group( 0 )
            num_part = match.group( 1 )
            # یافتن کلمهٔ برند در مچ
            brand_part = full_match.replace( num_part, "" ).strip()

            original = f"{brand_part} {num_part}"
            placeholder = cls._PLACEHOLDER_TEMPLATE.format( idx=idx )
            placeholders[ placeholder ] = original
            idx += 1
            return f"{brand_part} {placeholder}"

        masked = prefix_pat.sub( _replace_prefix, masked )

        # الگوی ۲: ترکیب حرف+عدد چسبیده (S24, A52, Note13)
        for inline_match in cls._INLINE_PATTERN.finditer( masked ):
            prefix = inline_match.group( 1 ).lower()
            if any( prefix.startswith( cue[ :3 ].lower() )
                    for cue in brand_cues ) or prefix in { "s", "a", "p", "se", "note", "redmi" }:
                original = inline_match.group( 0 )
                placeholder = cls._PLACEHOLDER_TEMPLATE.format( idx=idx )
                placeholders[ placeholder ] = original
                idx += 1
                masked = masked.replace( original, inline_match.group( 1 ) + placeholder, 1 )

        log_message( LG.NLU, f"{_RTL}ماسک مدل: {len(placeholders)} مورد شناسایی شد", LogLevel.DEBUG )
        return MaskResult( masked_text=masked, placeholders=placeholders )
