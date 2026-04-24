"""‫لودر و کش دانش دامنه (برندها، نگاشت‌های کیفی، قواعد استفاده)
‫مسئولیت: بارگذاری یک‌باره فایل JSON و ارائه دسترسی سریع و ایمن به NLU Pipeline
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

#───────────────────── local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG


class KnowledgeCache:
    """‫کش دانش دامنه برای دسترسی سریع در زمان اجرا"""
    _instance: "KnowledgeCache | None" = None
    _loaded: bool = False

    brands: frozenset[ str ]
    categories: frozenset[ str ]
    os_types: frozenset[ str ]
    colors: frozenset[ str ]
    qualitative_mappings: dict[ str, dict[ str, object ] ]
    use_case_rules: dict[ str, dict[ str, object ] ]
    intent_keywords: dict[ str, list[ str ] ]

    @classmethod
    def get_instance( cls, json_path: Path | None = None ) -> KnowledgeCache:
        if cls._instance is None:
            cls._instance = cls( json_path )
        return cls._instance

    def __init__( self, json_path: Path | None = None ) -> None:
        if self._loaded:
            return

        path = json_path or ( Path( __file__ ).parent / "domain_knowledge.json" )
        if not path.exists():
            raise FileNotFoundError( f"فایل دانش دامنه یافت نشد: {path}" )

        with path.open( "r", encoding="utf-8" ) as f:
            data: dict[ str, Any ] = json.load( f )

        self.brands = frozenset( data.get( "brands", [] ) )
        self.categories = frozenset( data.get( "categories", [] ) )
        self.os_types = frozenset( data.get( "os_types", [] ) )
        self.colors = frozenset( data.get( "colors", [] ) )
        self.qualitative_mappings = data.get( "qualitative_mappings", {} )
        self.use_case_rules = data.get( "use_case_rules", {} )
        self.intent_keywords = data.get( "intent_keywords", {} )

        self._loaded = True
        log_message( LG.NLU, f"✅ دانش دامنه بارگذاری شد | {len(self.brands)} برند | {len(self.qualitative_mappings)} نگاشت",
                     LogLevel.INFO )
