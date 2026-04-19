"""‫سرویس تولید بردارهای متنی (Dense Embedding) برای جستجوی معنایی"""
#───────────────────── Imports ─────────────────────
import warnings
from sentence_transformers import SentenceTransformer
import torch
from transformers import logging as transformers_logging

#───────────────────── Local Imports ─────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class EmbeddingService:
    """‫مدیریت مدل Embedding و تولید بردار (Dense)"""
    _instance: "EmbeddingService | None" = None

    def __init__( self ) -> None:
        settings = get_settings()
        path = settings.EMBEDDING_MODEL_PATH

        if not path.exists():
            raise FileNotFoundError( f"مسیر مدل Embedding یافت نشد: {path}" )

        # پیکربندی Torch برای پایداری محیط وب (جلوگیری از اشغال تمام هسته‌های CPU)
        torch.set_num_threads( 1 )
        warnings.filterwarnings( "ignore", message=".*UNEXPECTED.*" )
        transformers_logging.set_verbosity_error()

        self._model = SentenceTransformer( str( path ) )
        self._dimension = self._model.get_embedding_dimension()
        log_message( LG.RETRIEVAL, f"مدل Embedding بارگذاری شد | مسیر: {path} | ابعاد: {self._dimension}", LogLevel.INFO )

    @classmethod
    def get_instance( cls ) -> "EmbeddingService":
        """‫الگوی Singleton برای جلوگیری از بارگذاری مجدد مدل سنگین"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode( self, texts: str | list[ str ], is_query: bool = False ) -> list[ list[ float ] ]:
        """‫تبدیل متن به بردار نرمال‌شده

        Args:
            texts: یک رشته یا لیستی از رشته‌ها

        Returns:
            لیست بردارهای float با طول ثابت
        """
        input_texts = [ texts ] if isinstance( texts, str ) else texts
        # ✅ ‫افزودن پیشوند استاندارد E5
        prefix = "query: " if is_query else "passage: "
        formatted = [ f"{prefix}{t}" for t in input_texts ]
        embeddings = self._model.encode( formatted, normalize_embeddings=True )
        return embeddings.tolist()
