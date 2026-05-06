"""تشخیص و حل تضاد فیلترها بر اساس کانفیگ دامنه

⚠️ منسوخ‌شده (Deprecated): این ماژول به‌نفع LLMNLUExtractor کنار گذاشته شده است.
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG


@dataclass
class ConflictReport:
    """‫گزارش تضادهای یافت‌شده در فیلترها"""
    conflicts: list[ str ] = field( default_factory=list )
    removed_keys: list[ str ] = field( default_factory=list )
    warnings: list[ str ] = field( default_factory=list )

    @property
    def has_conflicts( self ) -> bool:
        return bool( self.conflicts )

    def summary( self ) -> str:
        if not self.has_conflicts: return "بدون تضاد"
        return f"تضاد‌ها: {', '.join(self.conflicts)} | حذف: {self.removed_keys}" if self.conflicts else "بدون تضاد"


class ConflictResolver:
    """حل‌کننده تضاد فیلترها با استراتژی‌های کانفیگ‌محور"""

    def __init__( self, domain_config: dict[ str, Any ] ) -> None:
        self._priority = tuple( domain_config.get( "conflict_resolution_order", [] ) )
        self._conflict_groups = domain_config.get( "conflict_groups", [] )

    def resolve( self, filters: dict[ str, Any ], original_text: str = "" ) -> tuple[ dict[ str, Any ], ConflictReport ]:
        report = ConflictReport()
        cleaned: dict[ str, Any ] = dict( filters )

        # ۱. بررسی تضاد در متن بر اساس گروه‌های کانفیگ
        for group in self._conflict_groups:
            terms = group.get( "terms", [] )
            strategy = group.get( "strategy", "drop_both" )
            present = [ t for t in terms if any( k in original_text for k in t ) ]
            if len( present ) > 1:
                report.conflicts.append( f"{group['id']}" )
                if strategy == "drop_both":
                    for slot in [ "price_range" ]:
                        if slot in cleaned:
                            report.removed_keys.append( slot )
                            report.warnings.append( f"حذف {slot} به‌خاطر تضاد متنی" )
                            cleaned.pop( slot, None )
                break

        if report.has_conflicts:
            log_message( LG.NLU, f"⚠️ تضاد در فیلترها | {report.summary()}", LogLevel.WARNING )

        return cleaned, report
