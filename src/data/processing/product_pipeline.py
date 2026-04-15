"""‫سرویس خط لولهٔ پردازش محصول (Raw → Transform → Enrich)
‫این ماژول مسئول خواندن دادهٔ خام از PostgreSQL، اعتبارسنجی، تبدیل به مدل دامنه و غنی‌سازی است.
‫ویژگی‌ها:
‫- اعتبارسنجی صریح با Pydantic
‫- جداسازی کامل لایه‌های Transform و Enrich (SRP)
‫- مدیریت خطای هدفمند و لاگینگ RTL
"""
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from src.config.logging_config import log_message, LogLevel, LG
from src.data.models.api.api_responses import DigikaiaProductDetailResponse
from src.data.models.core.product import Product
from src.data.repositories.product_repository import ProductRepository
from data.transformers.product_transformer import ProductTransformer
from src.services.product_enrichment_service import ProductEnrichmentService


class ProductProcessingPipeline:
    """‫خط لولهٔ تبدیل و غنی‌سازی محصولات خام"""

    def __init__( self,
                  repo: ProductRepository,
                  transformer: ProductTransformer | None = None,
                  enricher: ProductEnrichmentService | None = None ) -> None:
        self._repo = repo
        self._transformer = transformer or ProductTransformer()
        self._enricher = enricher or ProductEnrichmentService()

    async def process( self, product_id: int ) -> Product | None:
        """‫پردازش کامل یک محصول از حالت خام تا غنی‌شده

        Args:
            product_id: شناسهٔ محصول برای پردازش

        Returns:
            مدل Product غنی‌شده یا None در صورت عدم وجود داده/خطای اعتبارسنجی
        """
        log_message( LG.DATA_PROCESSING, f"شروع پردازش محصول {product_id}", LogLevel.DEBUG )

        try:
            raw_data = await self._repo.get_raw( product_id )
        except SQLAlchemyError as exc:
            log_message( LG.DATA_PROCESSING, f"خطای دیتابیس در خواندن محصول {product_id}: {exc}", LogLevel.ERROR )
            return None

        if raw_data is None:
            log_message( LG.DATA_PROCESSING, f"دادهٔ خام محصول {product_id} یافت نشد", LogLevel.WARNING )
            return None

        try:
            validated_response = DigikaiaProductDetailResponse.model_validate( raw_data )
        except ValidationError as exc:
            log_message( LG.DATA_PROCESSING, f"خطای اعتبارسنجی پاسخ API محصول {product_id}: {exc}", LogLevel.ERROR )
            return None

        api_product = validated_response.data.product

        try:
            product = self._transformer.transform( api_product )
        except ( ValueError, AttributeError, TypeError ) as exc:
            log_message( LG.DATA_PROCESSING, f"خطای تبدیل (Transformer) محصول {product_id}: {exc}", LogLevel.ERROR )
            return None

        try:
            enriched_product = self._enricher.enrich_product( product )
            log_message( LG.DATA_PROCESSING, f"محصول {product_id} با موفقیت غنی‌سازی شد", LogLevel.INFO )
            return enriched_product
        except ( ValueError, AttributeError, TypeError ) as exc:
            log_message( LG.DATA_PROCESSING, f"خطای غنی‌سازی (Enrichment) محصول {product_id}: {exc}", LogLevel.ERROR )
            return None
