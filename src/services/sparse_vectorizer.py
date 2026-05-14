"""سرویس تولید بردارهای تنک (Sparse) مبتنی بر توکنایز و حضور کلمات کلیدی"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import re
import zlib

#────────────────────────────────────────── Local  Imports  ──────────────────────────────────────────
from qdrant_client import models


class BM25Vectorizer:
    """‫تبدیل کوئری و اسناد به بردارهای Sparse با منطق Bag-of-Words (MVP)
    ‫⚠️ توجه: این پیاده‌سازی از وزن‌دهی باینری استفاده می‌کند (نه فرمول کامل BM25).
   ‫ برای سازگاری با Qdrant، ایندکس‌ها پیش از ساخت بردار مرتب‌سازی می‌شوند.
    """
    _TOKEN_PATTERN: re.Pattern[ str ] = re.compile( r'[\u0600-\u06FF\u0660-\u0669a-zA-Z0-9]{2,}' )
    _STOP_WORDS: frozenset[ str ] = frozenset(
        { "از", "به", "در", "با", "برای", "که", "و", "یا", "اگر", "نه", "بله", "این", "آن", "است" } )

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    @classmethod
    def query_to_sparse( cls, query: str ) -> models.SparseVector:
        """تبدیل متن کوئری به بردار‏ ‫ Sparse سازگار با Qdrant

        Args:
            query: متن ورودی کاربر

        Returns:
           ‫ مدل SparseVector با ایندکس‌های صعودی و مقادیر باینری
        """
        tokens = cls._tokenize( query )
        # ‫ استفاده از crc32 برای هش پایدار و cross-process + حذف خودکار تکرارها
        raw_indices = { zlib.crc32( t.encode( "utf-8" ) ) & 0xFFFFFFFF for t in tokens }

        # ‫ اصلاح حیاتی: مرتب‌سازی صعودی ایندکس‌ها مطابق قید سخت Qdrant برای Intersection/RRF
        sorted_indices = sorted( raw_indices )
        values = [ 1.0 ] * len( sorted_indices )

        return models.SparseVector( indices=sorted_indices, values=values )

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    @classmethod
    def _tokenize( cls, text: str ) -> list[ str ]:
        """توکنایز، نرمال‌سازی و حذف کلمات توقف

        Args:
            text: متن خام ورودی

        Returns:
            لیست توکن‌های فیلترشده و یکتا
        """
        return [ t for t in cls._TOKEN_PATTERN.findall( text.lower() ) if t not in cls._STOP_WORDS ]
