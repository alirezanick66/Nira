"""سرویس مرتب‌سازی نهایی نتایج (Cross-Encoder Reranker)
مسئولیت: دریافت کاندیداهای بازیابی‌شده، محاسبه امتیاز تطبیق دقیق کوئری-محصول،
و بازگرداندن بهترین نتایج برای لایه پاسخ‌دهی."""
from __future__ import annotations

import numpy as np
import onnxruntime as ort
import torch
from typing import Sequence, Any, cast
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedModel, PreTrainedTokenizerBase

from src.config.logging_config import LG, LogLevel, log_message
from src.config.settings import get_settings
from src.core.vector.qdrant_payload import QdrantProductPayload


class RerankerService:
    """سرویس Reranking با مدل bge-reranker-v2-m3 (بهینه برای CPU و فارسی)"""

    _instance: "RerankerService | None" = None
    _model: PreTrainedModel | None
    _session: ort.InferenceSession | None
    _tokenizer: PreTrainedTokenizerBase | None
    _batch_size: int

    def __init__( self ) -> None:
        settings = get_settings()
        self._batch_size = settings.RERANKER_BATCH_SIZE
        self._session = None
        self._model = None
        self._tokenizer = None

        # بررسی ایمن وجود تنظیمات ONNX
        if getattr( settings, "USE_ONNX", False ):
            onnx_path = getattr( settings, "ONNX_RERANKER_PATH", None )
            if onnx_path and ( onnx_path / "model_quantized.onnx" ).exists():
                self._session = ort.InferenceSession(
                    str( onnx_path / "model_quantized.onnx" ),
                    providers=[ "CPUExecutionProvider" ],
                )
                self._tokenizer = AutoTokenizer.from_pretrained( str( onnx_path ) )
                log_message( LG.RETRIEVAL, "سرویس Reranker (ONNX INT8) با موفقیت بارگذاری شد", LogLevel.INFO )
                return

        path = settings.RERANKER_MODEL_PATH
        if not path.exists():
            raise FileNotFoundError( f"مسیر مدل Reranker یافت نشد: {path}" )

        self._tokenizer = AutoTokenizer.from_pretrained( str( path ) )
        self._model = AutoModelForSequenceClassification.from_pretrained( str( path ) )

        # ✅ اصلاح خطای "eval is not a known attribute of None"
        if self._model is not None:
            self._model.eval()

        log_message( LG.RETRIEVAL, " ‫سرویس Reranker (PyTorch) بارگذاری شد", LogLevel.INFO )

    @classmethod
    def get_instance( cls ) -> "RerankerService":
        """الگوی Singleton برای جلوگیری از بارگذاری مجدد مدل"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _prepare_document_text( payload: QdrantProductPayload ) -> str:
        """ساخت متن طبیعی و غنی برای تطبیق بهتر با Cross-Encoder"""
        parts = [ payload.title ]
        if payload.expert_summary:
            parts.append( payload.expert_summary )
        elif payload.camera_summary:
            parts.append( f"دوربین: {payload.camera_summary}" )
        if payload.user_advantages:
            parts.append( "مزایا: " + "، ".join( payload.user_advantages[ :3 ] ) )
        if payload.price_range:
            parts.append( f"رنج قیمت: {payload.price_range}" )
        if payload.tags:
            parts.append( "ویژگی‌ها: " + "، ".join( payload.tags[ :3 ] ) )
        return " | ".join( filter( None, parts ) )

    def rerank( self, query: str, payloads: Sequence[ QdrantProductPayload ], top_k: int = 3 ) -> list[ QdrantProductPayload ]:
        if not payloads or not self._tokenizer:
            return list( payloads[ :top_k ] )

        try:
            # آماده‌سازی مستندات
            docs = [ self._prepare_document_text( p ) for p in payloads ]
            scores: list[ float ] = []

            # --- سناریو ONNX ---
            if self._session:
                for i in range( 0, len( docs ), self._batch_size ):
                    d_batch = docs[ i:i + self._batch_size ]
                    q_batch = [ query ] * len( d_batch )

                    # ✅ اصلاح خطای Tokenizer: ارسال صریح text و text_pair برای جلوگیری از ابهام تایپی
                    inputs = self._tokenizer( text=q_batch,
                                              text_pair=d_batch,
                                              padding=True,
                                              truncation=True,
                                              max_length=256,
                                              return_tensors="np" )

                    outputs = self._session.run( None, dict( inputs ) )

                    # ✅ اصلاح خطای squeeze: تبدیل خروجی به np.ndarray برای دسترسی به متدها
                    # خروجی session.run یک لیست است، پس ابتدا اولین عنصر را به آرایه تبدیل می‌کنیم.
                    logits = np.array( outputs[ 0 ] ).squeeze( axis=-1 )

                    # محاسبه Sigmoid روی آرایه
                    batch_scores_array = 1.0 / ( 1.0 + np.exp( -logits ) )

                    # ✅ اصلاح خطای tolist: مدیریت مقادیر اسکالر و آرایه
                    if batch_scores_array.ndim == 0:
                        scores.append( float( batch_scores_array ) )
                    else:
                        scores.extend( batch_scores_array.tolist() )

            # --- سناریو PyTorch ---
            elif self._model:
                model = self._model          # Narrowing برای تایپ‌چکر
                with torch.inference_mode():
                    for i in range( 0, len( docs ), self._batch_size ):
                        d_batch = docs[ i:i + self._batch_size ]
                        q_batch = [ query ] * len( d_batch )

                        inputs = self._tokenizer( text=q_batch,
                                                  text_pair=d_batch,
                                                  padding=True,
                                                  truncation=True,
                                                  max_length=256,
                                                  return_tensors="pt" )

                        # انتقال داده به دیوایس مدل (اگر مدل روی CUDA باشد)
                        inputs = { k: v.to( model.device ) for k, v in inputs.items() }

                        # ✅ اصلاح خطای squeeze در کلاس‌های نامشخص
                        outputs = model( **inputs )
                        logits = outputs.logits.squeeze( -1 )

                        # تبدیل به لیست پایتونی
                        batch_scores_tensor = torch.sigmoid( logits ).cpu()

                        # مدیریت خروجی تک‌مقدار یا لیستی
                        if batch_scores_tensor.ndim == 0:
                            scores.append( batch_scores_tensor.item() )
                        else:
                            scores.extend( batch_scores_tensor.tolist() )

            # مرتب‌سازی نهایی
            scored = sorted( zip( payloads, scores ), key=lambda x: x[ 1 ], reverse=True )
            log_message( LG.RETRIEVAL, f"✅ Reranking تکمیل | {len(payloads)} → {top_k} محصول", LogLevel.DEBUG )
            return [ p for p, _ in scored[ :top_k ] ]

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در Reranking، بازگشت به ترتیب اولیه: {exc}", LogLevel.WARNING )
            return list( payloads[ :top_k ] )
