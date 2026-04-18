"""‫سرویس بازیابی ترکیبی (Hybrid Retrieval) از Qdrant
‫مسئول: تبدیل کوئری متنی به بردارهای Dense + Sparse، اجرای جستجوی ترکیبی با RRF،
‫و اعمال فیلترهای متادیتا از خروجی NLU Pipeline
"""
from __future__ import annotations

import re

from qdrant_client import QdrantClient, models
from qdrant_client.models import ( Filter, FieldCondition, MatchValue, MatchAny, Range, Condition, Fusion, FusionQuery, Prefetch )

from src.services.embedding_service import EmbeddingService
from src.services.sparse_vectorizer import BM25Vectorizer
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_payload import QdrantProductPayload


class QdrantHybridRetriever:
    """‫بازیاب هوشمند با پشتیبانی از جستجوی معنایی + کلیدواژه‌ای + فیلتربرداری"""

    def __init__( self, client: QdrantClient | None = None, embedding_service: EmbeddingService | None = None ) -> None:
        self._settings = get_settings()
        self._client = client or QdrantClient( url=self._settings.QDRANT_URL, prefer_grpc=False )
        self._collection = self._settings.QDRANT_COLLECTION
        self._embedder = embedding_service or EmbeddingService.get_instance()
        log_message( LG.RETRIEVAL, "QdrantHybridRetriver Loaded", LogLevel.INFO )

    def _text_to_sparse_vector( self, query: str ) -> models.SparseVector:
        """‫تبدیل متن کوئری به بردار Sparse (شبیه‌سازی BM25 ساده برای MVP)"""
        tokens = re.findall( r'[\u0600-\u06FF\u0660-\u0669a-zA-Z0-9]{2,}', query.lower() )
        stop_words = { "از", "به", "در", "با", "برای", "که", "و", "یا", "اگر", "نه", "بله" }
        filtered = [ t for t in tokens if t not in stop_words ]

        indices = [ abs( hash( t ) ) % 10000 for t in set( filtered ) ]
        values = [ 1.0 ] * len( indices )
        return models.SparseVector( indices=indices, values=values )

    def _build_metadata_filter( self, filters: dict[ str, object ] | None ) -> Filter | None:
        """‫ساخت فیلتر Qdrant از دیکشنری فیلترهای NLU"""
        if not filters:
            return None

        must_conditions: list[ Condition ] = []          # ✅ رفع خطای Type Variance

        for key, value in filters.items():
            if isinstance( value, dict ):
                for op, val in value.items():
                    if op == "<": must_conditions.append( FieldCondition( key=key, range=Range( lt=val ) ) )
                    elif op == ">": must_conditions.append( FieldCondition( key=key, range=Range( gt=val ) ) )
                    elif op == "<=": must_conditions.append( FieldCondition( key=key, range=Range( lte=val ) ) )
                    elif op == ">=": must_conditions.append( FieldCondition( key=key, range=Range( gte=val ) ) )
            elif isinstance( value, list ):
                must_conditions.append( FieldCondition( key=key, match=MatchAny( any=value ) ) )
            elif isinstance( value, ( str, int, bool ) ):          # ✅ Narrowing برای رفع خطای MatchValue
                must_conditions.append( FieldCondition( key=key, match=MatchValue( value=value ) ) )

        return Filter( must=must_conditions ) if must_conditions else None

    def search( self, query: str, filters: dict[ str, object ] | None = None, top_k: int = 10 ) -> list[ QdrantProductPayload ]:
        """‫اجرای جستجوی ترکیبی واقعی (Dense Embedding + Sparse BM25) با RRF"""
        # ✅ تولید بردار واقعی به‌جای Placeholder
        dense_vec = self._embedder.encode( query, is_query=True )[ 0 ]
        sparse_vec = BM25Vectorizer.query_to_sparse( query )
        query_filter = self._build_metadata_filter( filters )

        result = self._client.query_points(
            collection_name=self._collection,
            prefetch=[
                Prefetch( query=dense_vec, using="dense", limit=top_k * 2 ),
                Prefetch( query=sparse_vec, using="sparse", limit=top_k * 2 ),
            ],
            query=FusionQuery( fusion=Fusion.RRF ),
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )

        payloads: list[ QdrantProductPayload ] = []
        for point in result.points:
            try:
                payload = QdrantProductPayload.model_validate( point.payload )
                payloads.append( payload )
            except Exception as exc:
                log_message( LG.RETRIEVAL, f"خطای اعتبارسنجی Payload محصول {point.id}: {exc}", LogLevel.WARNING )

        log_message( LG.RETRIEVAL, f"✅ {len(payloads)} محصول با Hybrid Search + RRF بازیابی شد", LogLevel.DEBUG )
        return payloads
