"""‫ردیاب پیشرفت همگام‌سازی برای قابلیت Resume (لایه ۴)"""
#───────────────────── Imports ─────────────────────
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import func

#───────────────────── Local Imports ─────────────────────
from src.data.db.models import SyncProgress
from src.data.db.engine import DatabaseEngine
from src.config.logging_config import log_message, LogLevel, LG


class ProgressTracker:
    """‫مدیریت نقطهٔ توقف و ادامهٔ خودکار همگام‌سازی"""

    def __init__( self, db_engine: DatabaseEngine ) -> None:
        self._db = db_engine

    async def load( self ) -> tuple[ int | None, int ]:
        """‫بارگذاری آخرین وضعیت: (last_processed_id, last_page)"""
        stmt = select( SyncProgress.last_processed_id, SyncProgress.last_page ).where( SyncProgress.id == 1 )
        async with self._db.session_maker() as session:
            result = await session.execute( stmt )
            row = result.one_or_none()
            return ( row[ 0 ], row[ 1 ] ) if row else ( None, 1 )

    async def save( self, product_id: int, page: int ) -> None:
        """‫ذخیره وضعیت فعلی (Upsert)"""
        stmt = ( pg_insert( SyncProgress ).values( id=1, last_processed_id=product_id, last_page=page,
                                                   updated_at=func.now() ).on_conflict_do_update(
                                                       index_elements=[ SyncProgress.id ],
                                                       set_=dict( last_processed_id=product_id,
                                                                  last_page=page,
                                                                  updated_at=func.now() ),
                                                   ) )

        async with self._db.session_maker() as session:
            await session.execute( stmt )
            await session.commit()
            log_message( LG.DATA_PROCESSING, f"Checkpoint ذخیره شد | ID: {product_id} | صفحه: {page}", LogLevel.DEBUG )
