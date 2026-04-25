"""سرویس تولید بردارهای متنی (Dense Embedding) برای جستجوی معنایی"""
#───────────────────── Imports ─────────────────────
from __future__ import annotations
import warnings
import numpy as np
import onnxruntime as ort
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, logging as transformers_logging, PreTrainedTokenizer

#───────────────────── Imports داخلی پروژه─────────────────────
from src.config.settings import Settings, get_settings
from src.config.logging_config import log_message, LogLevel, LG


class EmbeddingService:
    """مدیریت مدل Embedding و تولید بردار (Dense)"""

    def __init__( self, settings: Settings | None = None ) -> None:
        self._settings = settings or get_settings()
        self._session: ort.InferenceSession | None = None
        self._tokenizer: PreTrainedTokenizer | None = None
        self._model: SentenceTransformer | None = None
        self._dimension: int = 768
        self._use_onnx: bool = self._settings.USE_ONNX

        if self._use_onnx and ( self._settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx" ).exists():
            self._session = ort.InferenceSession(
                str( self._settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx" ),
                providers=[ "CPUExecutionProvider" ],
            )
            self._tokenizer = AutoTokenizer.from_pretrained( self._settings.ONNX_EMBEDDING_PATH )
            log_message( LG.RETRIEVAL, "سرویس Embedding (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )
            return

        self._use_onnx = False
        warnings.filterwarnings( "ignore", message=".*UNEXPECTED.*" )
        transformers_logging.set_verbosity_error()
        self._model = SentenceTransformer( str( self._settings.EMBEDDING_MODEL_PATH ) )
        dim = self._model.get_embedding_dimension()
        self._dimension = dim if dim else 768
        log_message( LG.RETRIEVAL, f"سرویس Embedding (PyTorch) بارگذاری شد | ابعاد: {self._dimension}", LogLevel.INFO )

    #───────────────────── public methods ─────────────────────
    def encode( self, texts: str | list[ str ], is_query: bool = False ) -> list[ list[ float ] ]:
        """تبدیل متن به بردار نرمال‌شده"""
        input_texts = [ texts ] if isinstance( texts, str ) else texts
        prefix = "query: " if is_query else "passage: "
        formatted = [ f"{prefix}{t}" for t in input_texts ]

        if self._use_onnx and self._session and self._tokenizer:
            inputs = self._tokenizer( formatted, padding=True, truncation=True, return_tensors="np" )
            outputs = self._session.run( None, dict( inputs ) )
            attention_mask = np.asarray( inputs[ "attention_mask" ] )
            pooled = self._mean_pooling( { "last_hidden_state": np.array( outputs[ 0 ] ) }, attention_mask )
            norms = np.linalg.norm( pooled, axis=1, keepdims=True )
            return ( pooled / norms ).tolist()

        if self._model is None:
            raise RuntimeError( "مدل Embedding بارگذاری نشده است." )
        embeddings = self._model.encode( formatted, normalize_embeddings=True )
        return embeddings.tolist()

    #───────────────────── private methods ─────────────────────
    @staticmethod
    def _mean_pooling( model_output: dict[ str, np.ndarray ], attention_mask: np.ndarray ) -> np.ndarray:
        """محاسبهٔ میانگین بردارها روی توکن‌ها (Mean Pooling برای مدل‌های E5)"""
        token_embeddings = model_output[ "last_hidden_state" ]
        input_mask_expanded = np.expand_dims( attention_mask, axis=-1 )
        sum_embeddings = np.sum( token_embeddings * input_mask_expanded, axis=1 )
        sum_mask = np.clip( np.sum( input_mask_expanded, axis=1 ), a_min=1e-9, a_max=None )
        return sum_embeddings / sum_mask
