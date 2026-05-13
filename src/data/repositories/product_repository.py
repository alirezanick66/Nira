"""ریپازیتوری مدیریت ذخیره و بازیابی داده‌های خام محصول
‫مسئولیت: تنها نقطهٔ تعامل با جدول product_raw_cache،
‫پیاده‌سازی الگوی Repository برای جداسازی لایهٔ داده از منطق تجاری.
"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────

from sqlalchemy import select, distinct
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

#────────────────────────────────────────── Local Imports ──────────────────────────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.engine import DatabaseEngine
from src.data.db.models import ProductRawCache


class ProductRepository:
    """‫مدیریت عملیات CRUD داده‌های خام API"""

    def __init__( self, db_engine: DatabaseEngine ) -> None:
        self._db = db_engine

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    async def save_raw( self, product_id: int, raw_data: dict[ str, object ] ) -> None:
        """ذخیره یا به‌روزرسانی داده خام محصول در جدول کش دیتابیس

       ‫ در صورت تکرار شناسه، عملیات Upsert انجام می‌شود.

        Args:
            product_id: شناسه محصول
            raw_data: دیکشنری داده خام برای ذخیره

        Raises:
            SQLAlchemyError: در صورت بروز خطای تراکنش در دیتابیس
        """
        stmt = ( pg_insert( ProductRawCache ).values( product_id=product_id, raw_payload=raw_data ).on_conflict_do_update(
            index_elements=[ ProductRawCache.product_id ], set_=dict( raw_payload=raw_data, updated_at=func.now() ) ) )
        async with self._db.session_maker() as session:
            try:
                await session.execute( stmt )
                await session.commit()
                log_message( LG.DATABASE, f"داده خام محصول {product_id} ذخیره/به‌روز شد", LogLevel.DEBUG )
            except SQLAlchemyError as exc:
                await session.rollback()
                log_message( LG.DATABASE, f"خطای تراکنش در ذخیره محصول {product_id}: {exc}", LogLevel.ERROR )
                raise

    async def get_raw( self, product_id: int ) -> dict[ str, object ] | None:
        """‫بازیابی داده خام از کش دیتابیس

        Args:
            product_id: شناسه محصول

        Returns:
           ‫ دیکشنری خام یا None در صورت عدم وجود
        """
        stmt = select( ProductRawCache.raw_payload ).where( ProductRawCache.product_id == product_id )
        async with self._db.session_maker() as session:
            try:
                result = await session.execute( stmt )
                return result.scalar_one_or_none()
            except SQLAlchemyError as exc:
                log_message( LG.DATABASE, f"خطای خواندن محصول {product_id}: {exc}", LogLevel.ERROR )
                return None

    async def list_raw_product_ids( self, limit: int | None = None ) -> list[ int ]:
        """‫دریافت لیست شناسه‌های محصولات خام از دیتابیس

        Args:
            limit: در صورت مقداردهی، تعداد نتایج را محدود می‌کند. مقادیر <1 نادیده گرفته می‌شوند.

        Returns:
            لیست شناسه‌های عددی
        """

        stmt = ( select( distinct( ProductRawCache.product_id ) ).order_by( ProductRawCache.product_id ) )

        if limit is not None and limit >= 1:
            stmt = stmt.limit( limit )

        async with self._db.session_maker() as session:
            result = await session.execute( stmt )
            return [ row[ 0 ] for row in result.all() ]

    async def batch_get_image_urls( self, product_ids: list[ int ] ) -> dict[ int, str | None ]:
        """استخراج لینک اولین تصویر  در لیست محصولات
                Args:
            product_ids: لیست شناسه محصولات

        Returns:
           ‫  لینک URL تصویر پس از از استخراج از دیتابیس  (در صورت عدم وجود: None)
        
        """
        if not product_ids:
            return {}

        prc = ProductRawCache

        # ‫استخراج مستقیم اولین آیتم آرایه از JSONB داخل PostgreSQL
        first_url = ( prc.raw_payload[ "data" ][ "product" ][ "images" ][ "webp_url" ].astext )

        stmt = ( select(
            prc.product_id,
            first_url,
        ).where( prc.product_id.in_( product_ids ) ) )

        async with self._db.session_maker() as session:
            result = await session.execute( stmt )

            # مستقیم dict بساز، بدون loop اضافه
            return { product_id: url if url else None for product_id, url in result }
