"""ماسک‌کردن هوشمند شماره مدل‌ها بر اساس کانفیگ دامنه"""
#─────────────────────IMPORTS─────────────────────
from dataclasses import dataclass, field

#─────────────────────Local Imports─────────────────────
from src.config.logging_config import log_message, LogLevel, LG


@dataclass( frozen=True )
class MaskResult:
    """‫نتیجهٔ ماسک‌کردن متن ورودی‫"""
    masked_text: str
    placeholders: dict[ str, str ] = field( default_factory=dict )


class ModelMasker:
    """شناساگر و ماسک‌کنندهٔ شماره مدل‌های چسبیده به پیشوندها"""

    @classmethod
    def mask( cls, text: str, model_prefixes: list[ str ] | frozenset[ str ] ) -> MaskResult:
        """ ‫جایگزینی پیشوند+عدد با placeholder ایمن"""
        if not model_prefixes:
            return MaskResult( masked_text=text )

        masked = text
        placeholders: dict[ str, str ] = {}
        idx = 0
        words = text.split()
        new_words: list[ str ] = []

        for w in words:
            is_model = False
            for p in model_prefixes:
                p_clean = p.lower().replace( "‌", "" ).replace( "-", "" )
                w_lower = w.lower()
                if w_lower.startswith( p_clean ) and len( w_lower ) > len( p_clean ) and w_lower[ len( p_clean ): ].isdigit():
                    placeholder = f"__MODEL_{idx}__"
                    placeholders[ placeholder ] = w
                    new_words.append( placeholder )
                    idx += 1
                    is_model = True
                    break
            if not is_model:
                new_words.append( w )

        result_text = " ".join( new_words )
        log_message( LG.NLU, f"🎭 ماسک مدل: {len(placeholders)} مورد شناسایی شد", LogLevel.DEBUG )
        return MaskResult( masked_text=result_text, placeholders=placeholders )
