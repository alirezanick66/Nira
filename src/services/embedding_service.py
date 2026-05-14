""" ‫سرویس تولید بردارهای متنی (Dense Embedding) برای جستجوی معنایی"""
#────────────────────────────────────────── Imports ──────────────────────────────────────────
from __future__ import annotations
import warnings
import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer, PreTrainedTokenizerBase
#────────────────────────────────────────── Local  Imports  ──────────────────────────────────────────
from src.config.settings import Settings, get_settings
from src.config.logging_config import log_message, LogLevel, LG


class EmbeddingService:
    """مدیریت مدل Embedding و تولید بردارهای Dense"""

    def __init__( self, settings: Settings | None = None ) -> None:
        self._settings = settings or get_settings()
        self._session: ort.InferenceSession | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None
        self._dimension: int = self._settings.EMBEDDING_DIM

        model_path = self._settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx"
        if not model_path.exists():
            raise FileNotFoundError( f"مسیر مدل ONNX Embedding یافت نشد: {model_path}" )

        self._init_onnx_session()

    def _init_onnx_session( self ) -> None:
        """ ‫راه‌اندازی نشست ONNX Runtime با بهینه‌سازی‌های CPU"""
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = getattr( self._settings, "ONNX_INTRA_THREADS", 0 )

        with warnings.catch_warnings():
            warnings.simplefilter( "ignore" )
            self._session = ort.InferenceSession(
                str( self._settings.ONNX_EMBEDDING_PATH / "model_quantized.onnx" ),
                sess_options=session_options,
                providers=list( getattr( self._settings, "ONNX_PROVIDERS", [ "CPUExecutionProvider" ] ) ),
            )
            self._tokenizer = AutoTokenizer.from_pretrained( str( self._settings.ONNX_EMBEDDING_PATH ) )
            if self._tokenizer is None:
                raise RuntimeError( "بارگذاری توکنایزر ONNX Embedding با شکست مواجه شد." )

        log_message( LG.RETRIEVAL, "سرویس Embedding (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    def encode( self, texts: str | list[ str ], is_query: bool = False ) -> list[ list[ float ] ]:
        """ ‫تبدیل متن به بردار نرمال‌شده (Cosine Normalized)

        Args:
            texts: متن ورودی یا لیست متون
            is_query: ‫اگر True باشد، پیشوند "query: " اضافه می‌شود

        Returns:
            لیست بردارهای نرمال‌شده

        Raises:
            RuntimeError: در صورت عدم بارگذاری موفق مدل یا توکنایزر
        """
        input_texts = [ texts ] if isinstance( texts, str ) else texts
        prefix = "query: " if is_query else "passage: "
        formatted = [ f"{prefix}{t}" for t in input_texts ]

        if not self._session or not self._tokenizer:
            raise RuntimeError( "سرویس Embedding به‌درستی راه‌اندازی نشده است." )

        try:
            return self._encode_onnx( formatted )
        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در تولید بردارهای Embedding: {exc}", LogLevel.ERROR )
            return [ [ 0.0 ] * self._dimension for _ in input_texts ]

    #────────────────────────────────────────── Private Methods ──────────────────────────────────────────
    def _encode_onnx( self, formatted_texts: list[ str ] ) -> list[ list[ float ] ]:
        """ ‫استنتاج بردارها با ONNX Runtime + Mean Pooling"""
        if self._session is None or self._tokenizer is None:
            raise RuntimeError( "ONNX Session یا Tokenizer راه‌اندازی نشده است." )

        inputs = self._tokenizer( formatted_texts, padding=True, truncation=True, return_tensors="np" )
        outputs = self._session.run( None, dict( inputs ) )
        attention_mask = np.asarray( inputs[ "attention_mask" ] )

        pooled = self._mean_pooling( { "last_hidden_state": np.array( outputs[ 0 ] ) }, attention_mask )
        norms = np.linalg.norm( pooled, axis=1, keepdims=True )
        return ( pooled / norms ).tolist()

    @staticmethod
    def _mean_pooling( model_output: dict[ str, np.ndarray ], attention_mask: np.ndarray ) -> np.ndarray:
        """ ‫محاسبهٔ میانگین بردارها روی توکن‌های فعال (مخصوص مدل‌های E5)"""
        token_embeddings = model_output[ "last_hidden_state" ]
        input_mask_expanded = np.expand_dims( attention_mask, axis=-1 )
        sum_embeddings = np.sum( token_embeddings * input_mask_expanded, axis=1 )
        sum_mask = np.clip( np.sum( input_mask_expanded, axis=1 ), a_min=1e-9, a_max=None )
        return sum_embeddings / sum_mask
