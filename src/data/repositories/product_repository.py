"""‫ریپازیتوری مدیریت ذخیره و بازیابی داده‌های خام محصول
‫این کلاس تنها نقطهٔ تعامل با جدول product_raw_cache است.
"""
#───────────────────── Imports ─────────────────────
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

#───────────────────── Local Imports ─────────────────────
from src.config.logging_config import log_message, LogLevel, LG
from src.data.db.engine import DatabaseEngine
from src.data.db.models import ProductRawCache


class ProductRepository:
    """‫مدیریت عملیات CRUD داده‌های خام API"""

    def __init__( self, db_engine: DatabaseEngine ) -> None:
        self._db = db_engine

    async def save_raw( self, product_id: int, raw_data: dict[ str, object ] ) -> None:

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
            دیکشنری خام یا None در صورت عدم وجود
        """
        stmt = select( ProductRawCache.raw_payload ).where( ProductRawCache.product_id == product_id )
        async with self._db.session_maker() as session:
            try:
                result = await session.execute( stmt )
                return result.scalar_one_or_none()
            except SQLAlchemyError as exc:
                log_message( LG.DATABASE, f"خطای خواندن محصول {product_id}: {exc}", LogLevel.ERROR )
                return None
