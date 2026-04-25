"""‫سرویس تولید بردارهای تنک (Sparse) مبتنی بر توکنایز و وزن‌دهی BM25"""
#───────────────────── Imports  ─────────────────────
import re
import zlib
#─────────────────────local imports─────────────────────
from qdrant_client import models


class BM25Vectorizer:
    """‫تبدیل کوئری و اسناد به بردارهای Sparse با منطق BM25 سبک (MVP)"""
    _TOKEN_PATTERN = re.compile( r'[\u0600-\u06FF\u0660-\u0669a-zA-Z0-9]{2,}' )
    _STOP_WORDS = frozenset( { "از", "به", "در", "با", "برای", "که", "و", "یا", "اگر", "نه", "بله", "این", "آن", "است" } )

    @classmethod
    def query_to_sparse( cls, query: str ) -> models.SparseVector:
        tokens = cls._tokenize( query )
        # ✅ جایگزینی hash() با zlib.crc32 برای تضمین یکتایی و پایداری بین ری‌استارت‌ها
        indices = [ zlib.crc32( t.encode( "utf-8" ) ) & 0xFFFFFFFF for t in set( tokens ) ]
        values = [ 1.0 ] * len( indices )
        return models.SparseVector( indices=indices, values=values )

    @classmethod
    def _tokenize( cls, text: str ) -> list[ str ]:
        """‫توکنایز، نرمال‌سازی و حذف کلمات توقف"""
        return [ t for t in cls._TOKEN_PATTERN.findall( text.lower() ) if t not in cls._STOP_WORDS ]
