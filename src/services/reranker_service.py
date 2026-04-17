"""‫سرویس مرتب‌سازی نهایی نتایج (Cross-Encoder Reranker)
‫مسئولیت: دریافت کاندیداهای بازیابی‌شده، محاسبه امتیاز تطبیق دقیق کوئری-محصول،
‫و بازگرداندن بهترین نتایج برای لایه پاسخ‌دهی.
"""
from __future__ import annotations

import torch
from pathlib import Path
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
        """‫ساخت متن فشرده و اطلاعاتی برای هر محصول جهت Reranking"""
        parts = [ payload.title ]
        if payload.camera_summary:
            parts.append( payload.camera_summary )
        if payload.user_advantages:
            parts.extend( payload.user_advantages[ :2 ] )          # دو مزیت اول کاربران
        parts.append( f"رنج قیمت: {payload.price_range}" )
        if payload.tags:
            parts.append( " | ".join( payload.tags[ :3 ] ) )
        return " | ".join( parts )

    def rerank(
            self,
            query: str,
            payloads: Sequence[ QdrantProductPayload ],
            top_k: int = 3,
            min_score: float = 0.3,          # ✅ کاهش آستانه برای MVP
    ) -> list[ QdrantProductPayload ]:
        """‫رتبه‌بندی مجدد محصولات بر اساس تطبیق معنایی دقیق کوئری"""
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

            # لاگ شفاف امتیازات برای دیباگ
            scored = sorted( zip( payloads, scores ), key=lambda x: x[ 1 ], reverse=True )
            for p, s in scored[ :top_k ]:
                log_message( LG.RETRIEVAL, f"  📊 {p.title[:40]}... | امتیاز: {s:.3f}", LogLevel.DEBUG )

            # فیلتر نرم + بازگشت top_k
            final = [ p for p, s in scored if s >= min_score ]
            return final[ :top_k ] if final else [ p for p, _ in scored[ :top_k ] ]

        except Exception as exc:
            log_message( LG.RETRIEVAL, f"خطا در Reranking، بازگشت به ترتیب اولیه: {exc}", LogLevel.WARNING )
            return list( payloads[ :top_k ] )
