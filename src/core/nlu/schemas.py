"""‫مدل‌های خروجی خط لوله درک زبان طبیعی (NLU)"""
from pydantic import BaseModel, Field
from typing import Literal
from typing import TypeAlias

# ‫تعریف صریح تایپ فیلترهای متادیتا برای انطباق با Qdrant و رعایت قانون ۶
NumericFilterValue: TypeAlias = int | float
RangeFilter: TypeAlias = dict[ str, NumericFilterValue ]
ListFilter: TypeAlias = list[ str ]
ScalarFilter: TypeAlias = str | int | float | bool
MetadataFilterValue: TypeAlias = RangeFilter | ListFilter | ScalarFilter
MetadataFilters: TypeAlias = dict[ str, MetadataFilterValue ]


class NLUIntent( BaseModel ):
    intent: Literal[ "search", "refine", "greeting", "compare" ] = Field( description="نیت کاربر" )
    requires_context: bool = Field( default=False, description="آیا نیاز به تاریخچه چت دارد؟" )


class NLUFilterQuery( BaseModel ):
    """‫ساختار نهایی خروجی NLU، آماده تزریق به QdrantHybridRetriever"""
    intent: str = Field( default="search" )
    semantic_query: str = Field( description="متن تمیزشده برای جستجوی برداری/کلیدواژه‌ای" )
    metadata_filters: MetadataFilters = Field( default_factory=dict, description="فیلترهای متادیتا سازگار با Qdrant" )
    is_greeting: bool = Field( default=False )
    warnings: list[ str ] = Field( default_factory=list, description="هشدارهای ConflictResolver یا اعتبارسنجی فیلتر" )
    sort_directive: dict[ str, str ] | None = Field(
        default=None, description="دایرکتیو مرتب‌سازی پس از Reranker: {'key': 'price', 'order': 'asc'|'desc'}" )


class FilterResolutionResult( BaseModel ):
    """‫نتیجه ادغام و حل تضاد بین فیلترهای صریح و استنتاجی"""
    metadata_filters: MetadataFilters = Field( default_factory=dict, description="فیلترهای نهایی پس از حل تضاد" )
    warnings: list[ str ] = Field( default_factory=list, description="هشدارهای تولیدشده در حین حل تضاد" )
