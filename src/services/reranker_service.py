"""سرویس مرتب‌سازی نهایی نتایج (Cross-Encoder Reranker)"""
#───────────────────── Imports  ─────────────────────
from __future__ import annotations
import numpy as np
import onnxruntime as ort
import torch
from typing import Sequence
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase

#───────────────────── Imports داخلی پروژه─────────────────────
from src.config.settings import Settings, get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_payload import QdrantProductPayload


class RerankerService:
    """ ‫سرویس Reranking با مدل bge-reranker-v2-m3 (بهینه برای CPU و فارسی)"""

    def __init__( self, settings: Settings | None = None ) -> None:
        self._settings = settings or get_settings()
        self._batch_size = self._settings.RERANKER_BATCH_SIZE
        self._min_score = self._settings.RERANKER_MIN_SCORE          # MVP Refinement
        self._session: ort.InferenceSession | None = None
        self._model: PreTrainedModel | None = None
        self._tokenizer: PreTrainedTokenizerBase | None = None

        if self._settings.USE_ONNX and ( self._settings.ONNX_RERANKER_PATH / "model_quantized.onnx" ).exists():
            self._session = ort.InferenceSession(
                str( self._settings.ONNX_RERANKER_PATH / "model_quantized.onnx" ),
                providers=[ "CPUExecutionProvider" ],
            )
            self._tokenizer = AutoTokenizer.from_pretrained( self._settings.ONNX_RERANKER_PATH )
            log_message( LG.RETRIEVAL, "سرویس Reranker (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )
            return

        path = self._settings.RERANKER_MODEL_PATH
        if not path.exists():
            raise FileNotFoundError( f"مسیر مدل Reranker یافت نشد: {path}" )

        self._tokenizer = AutoTokenizer.from_pretrained( str( path ) )
        self._model = AutoModelForSequenceClassification.from_pretrained( str( path ) )
        if self._model is not None:
            self._model.eval()          # ✅ ‫انتقال به __init__ برای جلوگیری از فراخوانی تکراری
        log_message( LG.RETRIEVAL, "سرویس Reranker (PyTorch) بارگذاری شد", LogLevel.INFO )

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
            query: کوئری کاربر
            payloads: نتایج بازیابی‌شده از Hybrid Search
            top_k: تعداد نهایی
            min_score: آستانه‌ی Sigmoid (پیش‌فرض: settings.RERANKER_MIN_SCORE).
                      ‫مقدار `0.0` برای غیرفعال کردن فیلتر.

        Returns:
            لیست محصولات مرتب‌شده (حداکثر top_k)
        """
        scored = self.rerank_with_scores( query, payloads )
        if not scored:
            return []

        threshold = self._min_score if min_score is None else min_score
        if threshold > 0.0:
            filtered = [ ( p, s ) for p, s in scored if s >= threshold ]
            if not filtered:
                # ‫اگر همه زیر آستانه هستند، حداقل بهترین را برگردان (Recall اولویت دارد)
                log_message(
                    LG.RETRIEVAL,
                    f"⚠️ هیچ نتیجه‌ای آستانه {threshold:.2f} را عبور نکرد - بازگشت به Top-1",
                    LogLevel.WARNING,
                )
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
        """‫نسخه‌ای از rerank که امتیازات Sigmoid را هم برمی‌گرداند.

        ‫مورد استفاده: کالیبراسیون آستانه (`scripts/calibrate_reranker.py`)
        """
        if not payloads or not self._tokenizer: return []

        try:
            queries = [ query ] * len( payloads )
            docs = [ self._prepare_document_text( p ) for p in payloads ]
            scores: list[ float ] = []

            if self._session and self._tokenizer:
                for i in range( 0, len( payloads ), self._batch_size ):
                    batch_q = queries[ i:i + self._batch_size ]
                    batch_d = docs[ i:i + self._batch_size ]
                    inputs = self._tokenizer(
                        text=batch_q,
                        text_pair=batch_d,
                        padding=True,
                        truncation=True,
                        max_length=256,
                        return_tensors="np",
                    )
                    outputs = self._session.run( None, dict( inputs ) )
                    logits = np.asarray( outputs[ 0 ] ).squeeze( axis=-1 )
                    batch_scores = 1.0 / ( 1.0 + np.exp( -logits ) )
                    scores.extend( batch_scores.tolist() if batch_scores.ndim != 0 else [ float( batch_scores ) ] )

            elif self._model and self._tokenizer:
                model = self._model
                with torch.inference_mode():
                    for i in range( 0, len( payloads ), self._batch_size ):
                        batch_q = queries[ i:i + self._batch_size ]
                        batch_d = docs[ i:i + self._batch_size ]
                        inputs = self._tokenizer(
                            text=batch_q,
                            text_pair=batch_d,
                            padding=True,
                            truncation=True,
                            max_length=256,
                            return_tensors="pt",
                        )
                        inputs = { k: v.to( model.device ) for k, v in inputs.items() }
                        outputs = model( **inputs ).logits.squeeze( -1 )
                        batch_scores = torch.sigmoid( outputs ).cpu().tolist()
                        scores.extend( batch_scores if isinstance( batch_scores, list ) else [ batch_scores ] )

            scored = sorted( zip( payloads, scores ), key=lambda x: x[ 1 ], reverse=True )
            return list( scored )

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در Reranking: {exc}", LogLevel.WARNING )
            return [ ( p, 0.0 ) for p in payloads ]

    @staticmethod
    def _prepare_document_text( payload: QdrantProductPayload ) -> str:
        parts = [ payload.title ]
        if payload.expert_summary: parts.append( payload.expert_summary )
        elif payload.camera_summary: parts.append( f"دوربین: {payload.camera_summary}" )
        if payload.user_advantages: parts.append( "مزایا: " + "، ".join( payload.user_advantages[ :3 ] ) )
        if payload.price_range: parts.append( f"رنج قیمت: {payload.price_range}" )
        if payload.tags: parts.append( "ویژگی‌ها: " + "، ".join( payload.tags[ :3 ] ) )
        return " | ".join( filter( None, parts ) )
