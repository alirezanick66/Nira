"""‫سرویس ایندکس‌سازی و مدیریت بردارهای محصولات در Qdrant
‫مسئول: ایجاد کالکشن، پیکربندی Hybrid (Dense+Sparse)، آپلود محصولات
"""
from typing import Sequence

from qdrant_client import QdrantClient, models
from qdrant_client.models import ( Distance, PayloadSchemaType )

from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from data.models.digikala.product import Product
from src.core.vector.qdrant_payload import QdrantProductPayload


class QdrantIndexer:
    """‫مدیریت اتصال، ساخت ایندکس و آپلود محصولات به Qdrant"""

    def __init__( self, client: QdrantClient | None = None ) -> None:
        self._settings = get_settings()
        self._client = client or QdrantClient( url=self._settings.QDRANT_URL, prefer_grpc=False, timeout=60 )
        self._collection = self._settings.QDRANT_COLLECTION

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

        # ‫ایندکس‌های Payload برای فیلتربرداری سریع (Rule 5: بدون Any)
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

        for prod in products:
            payload = QdrantProductPayload.from_product( prod )
            # ‫‫🟡 Placeholder: در گام بعدی، مدل Embedding واقعی برای dense و‫ BM25 برای sparse جایگزین می‌شود
            dense_vec = [ 0.0 ] * vector_size
            sparse_vec = models.SparseVector( indices=[], values=[] )

            points.append(
                models.PointStruct(
                    id=payload.product_id,
                    vector={
                        "dense": dense_vec,
                        "sparse": sparse_vec
                    },
                    payload=payload.model_dump( exclude_none=True ),
                ) )

        if points:
            self._client.upsert( collection_name=self._collection, points=points )
            log_message( LG.DATA_PROCESSING, f"{len(points)} محصول در Qdrant ایندکس شد", LogLevel.INFO )

        return len( points )
