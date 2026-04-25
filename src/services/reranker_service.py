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

    def rerank( self, query: str, payloads: Sequence[ QdrantProductPayload ], top_k: int = 3 ) -> list[ QdrantProductPayload ]:
        if not payloads or not self._tokenizer: return []

        try:
            pairs = [ ( query, self._prepare_document_text( p ) ) for p in payloads ]
            queries = [ query ] * len( payloads )
            docs = [ self._prepare_document_text( p ) for p in payloads ]
            scores: list[ float ] = []

            if self._session and self._tokenizer:
                for i in range( 0, len( pairs ), self._batch_size ):
                    inputs = self._tokenizer(
                        text=queries,
                        text_pair=docs,
                        padding=True,
                        truncation=True,
                        max_length=256,
                        return_tensors="np"          # یا "pt" برای شاخهٔ پایتورچ
                    )
                    outputs = self._session.run( None, dict( inputs ) )
                    logits = np.asarray( outputs[ 0 ] ).squeeze( axis=-1 )
                    batch_scores = 1.0 / ( 1.0 + np.exp( -logits ) )
                    scores.extend( batch_scores.tolist() if batch_scores.ndim != 0 else [ float( batch_scores ) ] )

            elif self._model and self._tokenizer:
                model = self._model
                with torch.inference_mode():
                    for i in range( 0, len( pairs ), self._batch_size ):
                        inputs = self._tokenizer(
                            text=queries,
                            text_pair=docs,
                            padding=True,
                            truncation=True,
                            max_length=256,
                            return_tensors="np"          # یا "pt" برای شاخهٔ پایتورچ
                        )
                        inputs = { k: v.to( model.device ) for k, v in inputs.items() }
                        outputs = model( **inputs ).logits.squeeze( -1 )
                        batch_scores = torch.sigmoid( outputs ).cpu().tolist()
                        scores.extend( batch_scores if isinstance( batch_scores, list ) else [ batch_scores ] )

            scored = sorted( zip( payloads, scores ), key=lambda x: x[ 1 ], reverse=True )
            log_message( LG.RETRIEVAL, f"✅ Reranking تکمیل | {len(payloads)} → {top_k} محصول", LogLevel.DEBUG )
            return [ p for p, _ in scored[ :top_k ] ]

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در Reranking، بازگشت به ترتیب اولیه: {exc}", LogLevel.WARNING )
            return list( payloads[ :top_k ] )

    @staticmethod
    def _prepare_document_text( payload: QdrantProductPayload ) -> str:
        parts = [ payload.title ]
        if payload.expert_summary: parts.append( payload.expert_summary )
        elif payload.camera_summary: parts.append( f"دوربین: {payload.camera_summary}" )
        if payload.user_advantages: parts.append( "مزایا: " + "، ".join( payload.user_advantages[ :3 ] ) )
        if payload.price_range: parts.append( f"رنج قیمت: {payload.price_range}" )
        if payload.tags: parts.append( "ویژگی‌ها: " + "، ".join( payload.tags[ :3 ] ) )
        return " | ".join( filter( None, parts ) )
