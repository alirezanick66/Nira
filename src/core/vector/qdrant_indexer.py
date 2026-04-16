"""‫سرویس ایندکس‌سازی و مدیریت بردارهای محصولات در Qdrant"""
from typing import Sequence

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.data.models.core.product import Product
from .qdrant_payload import QdrantProductPayload


class QdrantIndexer:
    """‫مدیریت اتصال، ساخت ایندکس و آپلود محصولات به Qdrant"""

    def __init__( self, client: QdrantClient | None = None ) -> None:
        self._settings = get_settings()
        self._client = client or QdrantClient( url=self._settings.QDRANT_URL, prefer_grpc=False )
        self._collection = self._settings.QDRANT_COLLECTION

    def ensure_collection( self, vector_size: int ) -> None:
        """‫ایجاد Collection و ایندکس‌های Payload در صورت عدم وجود"""
        if self._client.collection_exists( self._collection ):
            log_message( LG.DATA_PROCESSING, f"کالکشن {self._collection} از قبل موجود است", LogLevel.DEBUG )
            return

        self._client.create_collection(
            collection_name=self._collection,
            vectors_config=VectorParams( size=vector_size, distance=Distance.COSINE ),
        )
        log_message( LG.DATA_PROCESSING, f"کالکشن {self._collection} با موفقیت ایجاد شد", LogLevel.INFO )

        # ایجاد ایندکس برای فیلتربرداری سریع (Hybrid Search Ready)
        payload_indexes: dict[ str, PayloadSchemaType ] = {
            "price": PayloadSchemaType.INTEGER,
            "is_available": PayloadSchemaType.BOOL,
            "price_range": PayloadSchemaType.KEYWORD,
            "brand": PayloadSchemaType.KEYWORD,
            "tags": PayloadSchemaType.KEYWORD,
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
            # 🟡 جایگزینی با فراخوانی واقعی Embedding در گام بعدی
            vector = [ 0.0 ] * vector_size
            points.append( models.PointStruct(
                id=payload.product_id,
                vector=vector,
                payload=payload.model_dump( exclude_none=True ),
            ) )

        if points:
            self._client.upsert( collection_name=self._collection, points=points )
            log_message( LG.DATA_PROCESSING, f"{len(points)} محصول در Qdrant ایندکس شد", LogLevel.INFO )
        return len( points )
