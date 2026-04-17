"""‫مدل‌های خروجی خط لوله درک زبان طبیعی (NLU)"""
from pydantic import BaseModel, Field
from typing import Literal


class NLUIntent( BaseModel ):
    intent: Literal[ "search", "refine", "greeting", "compare" ] = Field( description="نیت کاربر" )
    requires_context: bool = Field( default=False, description="آیا نیاز به تاریخچه چت دارد؟" )


class NLUFilterQuery( BaseModel ):
    """‫ساختار نهایی خروجی NLU، آماده تزریق به QdrantHybridRetriever"""
    intent: str = Field( default="search" )
    semantic_query: str = Field( description="متن تمیزشده برای جستجوی برداری/کلیدواژه‌ای" )
    metadata_filters: dict = Field( default_factory=dict, description="فیلترهای متادیتا سازگار با Qdrant" )
    is_greeting: bool = Field( default=False )
