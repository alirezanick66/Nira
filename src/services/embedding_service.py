"""‫سرویس تولید بردارهای متنی (Dense Embedding) برای جستجوی معنایی"""
#───────────────────── Imports ─────────────────────
import warnings
from sentence_transformers import SentenceTransformer
import torch
from transformers import logging as transformers_logging
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer
#───────────────────── Local Imports ─────────────────────
from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG


class EmbeddingService:
    """‫مدیریت مدل Embedding و تولید بردار (Dense)"""
    _instance: "EmbeddingService | None" = None

    def __init__( self ) -> None:
        settings = get_settings()
        self._use_onnx = settings.USE_ONNX
        self._session = None
        self._tokenizer = None

        if self._use_onnx and ( settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx" ).exists():
            self._session = ort.InferenceSession( str( settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx" ),
                                                  providers=[ "CPUExecutionProvider" ] )
            self._tokenizer = AutoTokenizer.from_pretrained( settings.ONNX_EMBEDDING_PATH )
            self._dimension = 768
            log_message( LG.RETRIEVAL, "سرویس Embedding (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )
            return

        self._use_onnx = False
        warnings.filterwarnings( "ignore", message=".*UNEXPECTED.*" )
        transformers_logging.set_verbosity_error()
        self._model = SentenceTransformer( str( settings.EMBEDDING_MODEL_PATH ) )
        self._dimension = self._model.get_embedding_dimension()
        log_message( LG.RETRIEVAL, f" ‫سرویس Embedding (PyTorch) بارگذاری شد | ابعاد: {self._dimension}", LogLevel.INFO )

    @staticmethod
    def _mean_pooling( model_output: dict[ str, np.ndarray ], attention_mask: np.ndarray ) -> np.ndarray:
        """محاسبهٔ میانگین بردارها روی توکن‌ها (Mean Pooling برای مدل‌های E5)"""
        token_embeddings = model_output[ "last_hidden_state" ]
        input_mask_expanded = np.expand_dims( attention_mask, axis=-1 )
        sum_embeddings = np.sum( token_embeddings * input_mask_expanded, axis=1 )
        sum_mask = np.clip( np.sum( input_mask_expanded, axis=1 ), a_min=1e-9, a_max=None )
        return sum_embeddings / sum_mask

    @classmethod
    def get_instance( cls ) -> "EmbeddingService":
        """‫الگوی Singleton برای جلوگیری از بارگذاری مجدد مدل سنگین"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode( self, texts: str | list[ str ], is_query: bool = False ) -> list[ list[ float ] ]:
        """تبدیل متن به بردار نرمال‌شده"""
        input_texts = [ texts ] if isinstance( texts, str ) else texts
        prefix = "query: " if is_query else "passage: "
        formatted = [ f"{prefix}{t}" for t in input_texts ]

        if self._use_onnx and self._session and self._tokenizer:
            inputs = self._tokenizer( formatted, padding=True, truncation=True, return_tensors="np" )
            onnx_inputs = dict( inputs )
            outputs = self._session.run( None, onnx_inputs )
            pooled = self._mean_pooling( { "last_hidden_state": np.array( outputs[ 0 ] ) }, inputs[ "attention_mask" ] )
            norms = np.linalg.norm( pooled, axis=1, keepdims=True )
            return ( pooled / norms ).tolist()

        if self._model is None:
            raise RuntimeError( "مدل Embedding بارگذاری نشده است." )
        embeddings = self._model.encode( formatted, normalize_embeddings=True )
        return embeddings.tolist()
