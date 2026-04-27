"""‫سرویس بازیابی ترکیبی (Hybrid Retrieval) از Qdrant
‫مسئول: تبدیل کوئری متنی به بردارهای Dense + Sparse، اجرای جستجوی ترکیبی با RRF،
‫و اعمال فیلترهای متادیتا از خروجی NLU Pipeline

‫تغییرات MVP Refinement:
- Smart Fallback (0 Results): اگر هیچ نتیجه‌ای پیدا نشد، سخت‌ترین فیلتر را
  حذف کرده و دوباره جستجو می‌کند تا کاربر هرگز با لیست خالی مواجه نشود.
"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
from copy import deepcopy
from qdrant_client import QdrantClient
from qdrant_client.models import ( Filter, FieldCondition, MatchValue, MatchAny, Range, Condition, Fusion, FusionQuery, Prefetch )

#───────────────────── Local Imports ─────────────────────
from src.services.embedding_service import EmbeddingService
from src.services.sparse_vectorizer import BM25Vectorizer
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_payload import QdrantProductPayload


class QdrantHybridRetriever:
    """‫بازیاب هوشمند با پشتیبانی از جستجوی معنایی + کلیدواژه‌ای + فیلتربرداری"""

    # ‫ترتیب حذف فیلترها در Smart Fallback (سخت‌ترین → ساده‌ترین)
    # ‫فیلترهایی که در ابتدای لیست هستند، اول حذف می‌شوند.
    # ‫MVP Refinement #4: weight_g و camera_quality سخت‌گیرترین هستند.
    _RELAXATION_ORDER: tuple[ str, ... ] = (
        "weight_g",
        "battery_mah",
        "camera_quality",
        "battery_quality",
        "value_for_money",
        "ram_gb",
        "storage_gb",
        "tags",
        "price_range",
        "os",
        "price",
        "brand",          # ‫برند آخر حذف می‌شود (مهم‌ترین برای کاربر)
    )

    _MAX_RELAXATION_STEPS: int = 3          # ‫حداکثر سه فیلتر حذف می‌شود

    def __init__( self, client: QdrantClient | None = None, embedding_service: EmbeddingService | None = None ) -> None:
        self._settings = get_settings()
        self._client = client or QdrantClient( url=self._settings.QDRANT_URL, prefer_grpc=False )
        self._collection = self._settings.QDRANT_COLLECTION
        self._embedder = embedding_service or EmbeddingService()
        log_message( LG.RETRIEVAL, "QdrantHybridRetriever Loaded", LogLevel.INFO )

    #───────────────────── public  methods ─────────────────────
    def search(
        self,
        query: str,
        filters: dict[ str, object ] | None = None,
        top_k: int = 10,
        enable_fallback: bool = True,
    ) -> list[ QdrantProductPayload ]:
        """‫اجرای جستجوی ترکیبی واقعی (Dense Embedding + Sparse BM25) با RRF

        ‫MVP Refinement #4: در صورت عدم یافتن نتیجه، فیلترهای سخت به‌ترتیب حذف می‌شوند
        ‫تا حداکثر `_MAX_RELAXATION_STEPS` بار - بدون افت کیفیت در فیلترهای کلیدی (برند).

        Args:
            query: متن کوئری
            filters: فیلترهای متادیتا (خروجی NLU)
            top_k: تعداد نتایج
            enable_fallback: فعال‌سازی Smart Fallback (پیش‌فرض: True)

        Returns:
            لیست QdrantProductPayload (ممکن است با فیلترهای ریلکس‌شده برگردد)
        """
        # ‫تولید بردار یک‌بار (مستقل از فیلتر) → بهینه‌سازی fallback
        dense_vec = self._embedder.encode( query, is_query=True )[ 0 ]
        sparse_vec = BM25Vectorizer.query_to_sparse( query )

        # ‫تلاش 1: با فیلترهای کامل
        results = self._execute_search( dense_vec, sparse_vec, filters, top_k )
        if results or not enable_fallback or not filters:
            log_message(
                LG.RETRIEVAL,
                f"✅ {len(results)} محصول با Hybrid Search + RRF بازیابی شد",
                LogLevel.DEBUG,
            )
            return results

        # ‫تلاش‌های Fallback: حذف تدریجی فیلترهای سخت
        log_message(
            LG.RETRIEVAL,
            "🔄 Smart Fallback فعال شد - تلاش با حذف فیلترهای سخت‌گیر",
            LogLevel.INFO,
        )

        relaxed_filters = deepcopy( filters )
        for step in range( self._MAX_RELAXATION_STEPS ):
            removed_key = self._relax_one_filter( relaxed_filters )
            if removed_key is None:
                # ‫دیگر فیلتری برای حذف نمانده
                break

            log_message(
                LG.RETRIEVAL,
                f"  ↻ گام {step+1}: فیلتر «{removed_key}» حذف شد، تلاش مجدد...",
                LogLevel.INFO,
            )

            results = self._execute_search( dense_vec, sparse_vec, relaxed_filters, top_k )
            if results:
                log_message(
                    LG.RETRIEVAL,
                    f"✅ Fallback موفق در گام {step+1} | {len(results)} محصول | فیلترهای فعال: {list(relaxed_filters.keys())}",
                    LogLevel.INFO,
                )
                return results

        # ‫تلاش نهایی: بدون هیچ فیلتری (فقط جستجوی برداری)
        log_message(
            LG.RETRIEVAL,
            "🆘 آخرین تلاش: جستجو بدون فیلتر",
            LogLevel.WARNING,
        )
        results = self._execute_search( dense_vec, sparse_vec, None, top_k )
        log_message(
            LG.RETRIEVAL,
            f"✅ {len(results)} محصول با Fallback نهایی بازیابی شد",
            LogLevel.DEBUG,
        )
        return results

    #───────────────────── private  methods ─────────────────────
    def _execute_search(
        self,
        dense_vec,
        sparse_vec,
        filters: dict[ str, object ] | None,
        top_k: int,
    ) -> list[ QdrantProductPayload ]:
        """‫اجرای یک تلاش جستجو با فیلترهای داده‌شده"""
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
                log_message(
                    LG.RETRIEVAL,
                    f"خطای اعتبارسنجی Payload محصول {point.id}: {exc}",
                    LogLevel.WARNING,
                )

        return payloads

    def _relax_one_filter( self, filters: dict[ str, object ] ) -> str | None:
        """‫حذف سخت‌ترین فیلتر باقی‌مانده طبق `_RELAXATION_ORDER`

        Args:
            filters: دیکشنری فیلترها (به‌صورت in-place اصلاح می‌شود)

        Returns:
            نام فیلتر حذف‌شده، یا None اگر دیگر فیلتری برای حذف نباشد.
        """
        for key in self._RELAXATION_ORDER:
            if key in filters:
                del filters[ key ]
                return key
        # ‫اگر کلیدهای ناشناخته در filters باشند، یکی از آن‌ها را حذف می‌کنیم
        if filters:
            unknown_key = next( iter( filters ) )
            del filters[ unknown_key ]
            return unknown_key
        return None

    def _build_metadata_filter( self, filters: dict[ str, object ] | None ) -> Filter | None:
        """ساخت فیلتر Qdrant از دیکشنری فیلترهای NLU با تایپ‌دهی صریح"""
        if not filters:
            return None

        must_conditions: list[ Condition ] = []

        for key, value in filters.items():
            if isinstance( value, dict ):
                for op, val in value.items():
                    if op == "<": must_conditions.append( FieldCondition( key=key, range=Range( lt=val ) ) )
                    elif op == ">": must_conditions.append( FieldCondition( key=key, range=Range( gt=val ) ) )
                    elif op == "<=": must_conditions.append( FieldCondition( key=key, range=Range( lte=val ) ) )
                    elif op == ">=": must_conditions.append( FieldCondition( key=key, range=Range( gte=val ) ) )
            elif isinstance( value, list ):
                must_conditions.append( FieldCondition( key=key, match=MatchAny( any=value ) ) )
            elif isinstance( value, ( str, int, bool ) ):
                must_conditions.append( FieldCondition( key=key, match=MatchValue( value=value ) ) )

        return Filter( must=must_conditions ) if must_conditions else None
