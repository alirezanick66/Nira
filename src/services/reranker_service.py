"""‫سرویس مرتب‌سازی نهایی نتایج (Cross-Encoder Reranker)
‫مسئولیت: دریافت کاندیداهای بازیابی‌شده، محاسبه امتیاز تطبیق دقیق کوئری-محصول،
‫و بازگرداندن بهترین نتایج برای لایه پاسخ‌دهی.
"""
from __future__ import annotations

import torch
from typing import Sequence
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from src.config.settings import get_settings
from src.config.logging_config import log_message, LogLevel, LG
from src.core.vector.qdrant_payload import QdrantProductPayload


class RerankerService:
    """‫سرویس Reranking با مدل bge-reranker-v2-m3 (بهینه برای CPU و فارسی)"""
    _instance: "RerankerService | None" = None

    def __init__( self ) -> None:
        settings = get_settings()
        path = settings.RERANKER_MODEL_PATH

        if not path.exists():
            raise FileNotFoundError( f"مسیر مدل Reranker یافت نشد: {path}" )

        self._tokenizer = AutoTokenizer.from_pretrained( str( path ) )
        self._model = AutoModelForSequenceClassification.from_pretrained( str( path ) )
        self._model.eval()
        self._batch_size = settings.RERANKER_BATCH_SIZE
        log_message( LG.RETRIEVAL, "سرویس Reranker با موفقیت بارگذاری شد", LogLevel.INFO )

    @classmethod
    def get_instance( cls ) -> "RerankerService":
        """‫الگوی Singleton برای جلوگیری از بارگذاری مجدد مدل"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def _prepare_document_text( payload: QdrantProductPayload ) -> str:
        """‫ساخت متن طبیعی و غنی برای تطبیق بهتر با Cross-Encoder"""
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

    def rerank(
        self,
        query: str,
        payloads: Sequence[ QdrantProductPayload ],
        top_k: int = 3,
    ) -> list[ QdrantProductPayload ]:
        """‫رتبه‌بندی مجدد محصولات (بدون آستانهٔ مطلق برای پایداری MVP)"""
        if not payloads:
            return []

        try:
            pairs = [ ( query, self._prepare_document_text( p ) ) for p in payloads ]
            scores: list[ float ] = []

            for i in range( 0, len( pairs ), self._batch_size ):
                batch = pairs[ i:i + self._batch_size ]
                inputs = self._tokenizer( batch, padding=True, truncation=True, max_length=256, return_tensors="pt" )
                with torch.inference_mode():
                    outputs = self._model( **inputs ).logits.squeeze( -1 )
                    batch_scores = torch.sigmoid( outputs ).cpu().tolist()
                    if isinstance( batch_scores, float ):
                        batch_scores = [ batch_scores ]
                    scores.extend( batch_scores )

            # مرتب‌سازی نسبی (بدون حذف بر اساس آستانهٔ مطلق)
            scored = sorted( zip( payloads, scores ), key=lambda x: x[ 1 ], reverse=True )

            log_message( LG.RETRIEVAL, f"✅ Reranking تکمیل | {len(payloads)} → {top_k} محصول", LogLevel.DEBUG )
            return [ p for p, _ in scored[ :top_k ] ]

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در Reranking، بازگشت به ترتیب RRF: {exc}", LogLevel.WARNING )
            return list( payloads[ :top_k ] )
