"""‫سرویس ایندکس‌سازی و مدیریت بردارهای محصولات در Qdrant
‫مسئول: ایجاد کالکشن، پیکربندی Hybrid (Dense+Sparse)، آپلود محصولات
"""
#───────────────────── Imports ─────────────────────
from typing import Sequence
from qdrant_client import QdrantClient, models
from qdrant_client.models import ( Distance, PayloadSchemaType )

#───────────────────── Local Imports ─────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.data.models.product import Product
from src.core.vector.qdrant_payload import QdrantProductPayload
from src.services.embedding_service import EmbeddingService
from src.services.sparse_vectorizer import BM25Vectorizer


class QdrantIndexer:
    """‫مدیریت اتصال، ساخت ایندکس و آپلود محصولات به Qdrant"""

    def __init__( self, client: QdrantClient | None = None, embedding_service: EmbeddingService | None = None ) -> None:
        self._settings = get_settings()
        self._client = client or QdrantClient( url=self._settings.QDRANT_URL, prefer_grpc=False, timeout=60 )
        self._collection = self._settings.QDRANT_COLLECTION
        self._embedder = embedding_service or EmbeddingService()
        log_message( LG.DATA_PROCESSING, "QdrantIndexer با سرویس Embedding فعال راه‌اندازی شد", LogLevel.INFO )

    #───────────────────── Public Methods ─────────────────────
    def ensure_collection( self, vector_size: int ) -> None:
        """‫ایجاد Collection و ایندکس‌های Payload در صورت عدم وجود"""
        if self._client.collection_exists( self._collection ):
            log_message( LG.DATA_PROCESSING, f"کالکشن {self._collection} از قبل موجود است", LogLevel.DEBUG )
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                "dense": models.VectorParams( size=vector_size, distance=Distance.COSINE ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams( index=models.SparseIndexParams( on_disk=False ) ),
            },
        )
        log_message( LG.DATA_PROCESSING, f"کالکشن {self._collection} با پشتیبانی Hybrid ایجاد شد", LogLevel.INFO )

        # ‫ایندکس‌های Payload برای فیلتربرداری سریع
        # ‫MVP Refinement: ایندکس واحدها برای فیلتر دقیق GB/MB/TB
        payload_indexes: dict[ str, PayloadSchemaType ] = {
            "price": PayloadSchemaType.INTEGER,
            "is_available": PayloadSchemaType.BOOL,
            "has_discount": PayloadSchemaType.BOOL,
            "discount_percent": PayloadSchemaType.INTEGER,
            "price_range": PayloadSchemaType.KEYWORD,
            "brand": PayloadSchemaType.KEYWORD,
            "os": PayloadSchemaType.KEYWORD,
            "tags": PayloadSchemaType.KEYWORD,
            "ram_gb": PayloadSchemaType.INTEGER,
            "ram_unit": PayloadSchemaType.KEYWORD,
            "storage_gb": PayloadSchemaType.INTEGER,
            "storage_unit": PayloadSchemaType.KEYWORD,
            "battery_mah": PayloadSchemaType.INTEGER,
            "battery_unit": PayloadSchemaType.KEYWORD,
            "battery_quality": PayloadSchemaType.KEYWORD,
            "camera_quality": PayloadSchemaType.KEYWORD,
            "value_for_money": PayloadSchemaType.KEYWORD,
        }
        for field, schema_type in payload_indexes.items():
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema=schema_type,
            )
        log_message( LG.DATA_PROCESSING, "ایندکس‌های Payload با موفقیت ایجاد شدند", LogLevel.DEBUG )

    def index_products( self, products: Sequence[ Product ], vector_size: int ) -> int:
        """‫تبدیل، بردارسازی و آپلود محصولات به Qdrant

        Args:
            products: لیست محصولات پردازش‌شده
            vector_size: ابعاد بردار مدل Embedding

        Returns:
            تعداد محصولات ایندکس‌شده
        """
        self.ensure_collection( vector_size )
        points = []

        texts = [ f"passage: {p.title}" for p in products ]
        dense_vectors = self._embedder.encode( texts, is_query=False )

        for idx, prod in enumerate( products ):
            payload = QdrantProductPayload.from_product( prod )
            sparse_vec = BM25Vectorizer.query_to_sparse( payload.search_text or payload.title )

            points.append(
                models.PointStruct(
                    id=payload.product_id,
                    vector={
                        "dense": dense_vectors[ idx ],
                        "sparse": sparse_vec
                    },
                    payload=payload.model_dump( exclude_none=True ),
                ) )

        if points:
            self._client.upsert( collection_name=self._collection, points=points )
            log_message( LG.DATA_PROCESSING, f"{len(points)} محصول در Qdrant ایندکس شد", LogLevel.INFO )

        return len( points )
