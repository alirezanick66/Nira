""" ‫سرویس مرتب‌سازی نهایی نتایج (Cross-Encoder Reranker)"""
#────────────────────────────────────────── Imports  ──────────────────────────────────────────
from __future__ import annotations
import numpy as np
import onnxruntime as ort
from typing import Sequence
from transformers import AutoTokenizer, PreTrainedTokenizerBase
import warnings
#────────────────────────────────────────── Local  Imports ──────────────────────────────────────────
from src.config.settings import Settings, get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_payload import QdrantProductPayload


class RerankerService:
    """ ‫سرویس Reranking با مدل bge-reranker-v2-m3 (بهینه برای CPU و فارسی)"""

    def __init__( self, settings: Settings | None = None ) -> None:
        self._settings = settings or get_settings()
        self._batch_size = self._settings.RERANKER_BATCH_SIZE
        self._min_score = self._settings.RERANKER_MIN_SCORE          # MVP Refinement
        self._session: ort.InferenceSession
        self._tokenizer: PreTrainedTokenizerBase

        model_path = self._settings.ONNX_RERANKER_PATH / "model_quantized.onnx"
        if not model_path.exists():
            raise FileNotFoundError( f"مسیر مدل Reranker یافت نشد: {model_path}" )

        # بارگذاری مدل با بهینه‌سازی CPU
        self._init_onnx_session()

        # بارگذاری توکنایزر
        self._tokenizer = AutoTokenizer.from_pretrained( str( self._settings.ONNX_RERANKER_PATH ) )
        if self._tokenizer is None:
            raise RuntimeError( "بارگذاری توکنایزر Reranker با شکست مواجه شد." )

    #────────────────────────────────────────── Public methods ──────────────────────────────────────────
    def rerank(
        self,
        query: str,
        payloads: Sequence[ QdrantProductPayload ],
        top_k: int = 3,
        min_score: float | None = None,
    ) -> list[ QdrantProductPayload ]:
        """‫مرتب‌سازی نتایج با حذف نتایج زیر آستانه `min_score`

        ‫MVP Refinement: اعمال آستانه فیلتر برای کاهش نتایج نامرتبط در Top-k.

        Args:
            query: کوئری ورودی کاربر
            payloads:‫نتایج بازیابی‌شده از Hybrid Search
            top_k: تعداد نهایی محصولات پس از فیلتر
            min_score: ‫آستانهٔ امتیاز (پیش‌فرض: مقدار تعریف‌شده در settings)
                

        Returns:
            لیست مرتب‌شدهٔ محصولات (حداکثر top_k عدد)
        """
        scored = self.rerank_with_scores( query, payloads )
        if not scored:
            return []

        for product, score in scored:
            log_message( LG.RETRIEVAL, f"📊 Reranker score: {score:.4f} | {product.title[:40]}", LogLevel.DEBUG )

        threshold = self._min_score if min_score is None else min_score
        if threshold > 0.0:
            filtered = [ ( p, s ) for p, s in scored if s >= threshold ]
            if not filtered:
                # ‫اگر همه زیر آستانه هستند، حداقل بهترین را برگردان (Recall اولویت دارد)
                log_message( LG.RETRIEVAL, f"⚠️ هیچ نتیجه‌ای آستانه {threshold:.2f} را عبور نکرد - بازگشت به Top-1",
                             LogLevel.WARNING )
                filtered = scored[ :1 ]
        else:
            filtered = scored

        result = [ p for p, _ in filtered[ :top_k ] ]
        log_message(
            LG.RETRIEVAL,
            f"✅ Reranking تکمیل | {len(payloads)} → {len(result)} محصول (آستانه={threshold:.2f})",
            LogLevel.DEBUG,
        )
        return result

    def rerank_with_scores( self, query: str,
                            payloads: Sequence[ QdrantProductPayload ] ) -> list[ tuple[ QdrantProductPayload, float ] ]:
        """محاسبهٔ امتیاز تطابق کوئری با هر سند و مرتب‌سازی نزولی

        Args:
            query: متن کوئری کاربر
            payloads: لیست محصولات کاندید برای رتبه‌بندی

        Returns:
            لیست تاپل‌های (محصول, امتیاز) مرتب‌شده بر اساس بیشترین شباهت

        Raises:
            RuntimeError: ‫در صورت شکست استنتاج ONNX Runtime
        """
        if not payloads or not self._tokenizer or not self._session:
            return []

        try:
            queries = [ query ] * len( payloads )
            docs = [ self._prepare_document_text( p ) for p in payloads ]
            scores: list[ float ] = []

            for i in range( 0, len( payloads ), self._batch_size ):
                batch_q = queries[ i:i + self._batch_size ]
                batch_d = docs[ i:i + self._batch_size ]
                inputs = self._tokenizer(
                    text=batch_q,
                    text_pair=batch_d,
                    padding=True,
                    truncation=True,
                    return_tensors="np",
                )
                outputs = self._session.run( None, dict( inputs ) )
                logits = np.asarray( outputs[ 0 ] ).squeeze( axis=-1 )
                batch_scores = 1.0 / ( 1.0 + np.exp( -logits ) )
                scores.extend( batch_scores.tolist() if batch_scores.ndim != 0 else [ float( batch_scores ) ] )

            indices = np.argsort( scores )[ ::-1 ].tolist()
            return [ ( payloads[ idx ], scores[ idx ] ) for idx in indices ]

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطای بحرانی در Reranking: {exc}", LogLevel.ERROR )
            raise RuntimeError( "سرویس Reranking در استنتاج مدل با شکست مواجه شد" ) from exc

    @staticmethod
    def _prepare_document_text( payload: QdrantProductPayload ) -> str:
        """تولید متن بهینه از Payload برای تزریق به Cross-Encoder

        Args:
            payload: داده‌های ساختاریافته محصول

        Returns:
            رشتهٔ ترکیبی شامل عنوان، قیمت، مشخصات کلیدی و بازخورد کاربران
        """
        parts: list[ str ] = [ payload.title ]

        # ‫قیمت واقعی — حیاتی برای کوئری‌های عددی قیمت
        if payload.price and payload.price > 0:
            price_m = payload.price / 1_000_000
            parts.append( f"قیمت: {price_m:.1f} میلیون تومان ({payload.price_range})" )

        # ‫مشخصات فنی کلیدی
        specs: list[ str ] = []
        if payload.ram_gb:
            specs.append( f"رم {payload.ram_gb}GB" )
        if payload.storage_gb:
            specs.append( f"حافظه {payload.storage_gb}GB" )
        if payload.battery_mah:
            specs.append( f"باتری {payload.battery_mah}mAh" )
        if payload.camera_mp:
            specs.append( f"دوربین {payload.camera_mp}MP" )
        if specs:
            parts.append( " | ".join( specs ) )

        # ‫خلاصه تخصصی یا دوربین
        if payload.expert_summary:
            parts.append( payload.expert_summary )
        elif payload.camera_summary:
            parts.append( f"دوربین: {payload.camera_summary}" )

        # ‫مزایای کاربران
        if payload.user_advantages:
            parts.append( "مزایا: " + "، ".join( payload.user_advantages[ :3 ] ) )

        # ‫برچسب‌های کیفی
        if payload.tags:
            parts.append( "ویژگی‌ها: " + "، ".join( payload.tags[ :4 ] ) )

        return " | ".join( filter( None, parts ) )

    def _init_onnx_session( self ) -> None:
        """ ‫راه‌اندازی نشست ONNX Runtime با بهینه‌سازی‌های CPU"""
        session_options = ort.SessionOptions()
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.intra_op_num_threads = getattr( self._settings, "ONNX_INTRA_THREADS", 0 )

        with warnings.catch_warnings():
            warnings.simplefilter( "ignore" )
            self._session = ort.InferenceSession(
                str( self._settings.ONNX_RERANKER_PATH / "model_quantized.onnx" ),
                sess_options=session_options,
                providers=list( getattr( self._settings, "ONNX_PROVIDERS", [ "CPUExecutionProvider" ] ) ),
            )

        log_message( LG.RETRIEVAL, "سرویس Reranking (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )
