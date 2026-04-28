"""اسکریپت واحد تبدیل و کوانتایز کردن مدل‌ها  ‫به ONNX (Dynamic INT8)

قابلیت‌ها:
- ‫پشتیبانی از هر مدل Transformer (Embedding, Reranker, Classification, ...)
- ‫دو حالت اجرا: standard (سریع‌تر) و low-memory (برای مدل‌های بزرگ)
- ‫skip خودکار اگر خروجی از قبل موجود باشد
- ‫قابل import به عنوان ماژول

نمونه استفاده:
    from quantize_unified import quantize_model, quantize_from_settings

    # برای یک مدل دلخواه
    quantize_model(
        model_class_name="feature_extraction",
        src=Path("./e5"),
        dst=Path("./onnx_e5"),
        low_memory=False,
        model_label="E5",
    )

    #‫ یا استفاده از settings.py پروژه
    quantize_from_settings(low_memory_reranker=True)
"""

#─────────────────────IMPORT─────────────────────
import gc
from pathlib import Path
from typing import Literal

try:
    import torch
except ImportError:
    torch = None

#─────────────────────LOCAL IMPORT─────────────────────
from transformers import AutoTokenizer
from optimum.onnxruntime import ( ORTModelForFeatureExtraction, ORTModelForSequenceClassification, ORTQuantizer )
from optimum.onnxruntime.configuration import AutoQuantizationConfig

from src.config.logging_config import log_message, LogLevel, LG

# ── mapping ساده‌ی کلاس‌های مدل ──
MODEL_CLASS_MAP = {
    "feature_extraction": ORTModelForFeatureExtraction,
    "sequence_classification": ORTModelForSequenceClassification,
}


def _free_memory() -> None:
    """ ‫آزادسازی RAM و VRAM (اگر CUDA موجود باشد)."""
    gc.collect()
    if torch is not None and torch.cuda.is_available():
        torch.cuda.empty_cache()
        log_message( LG.RETRIEVAL, "🧹 CUDA cache پاک شد", LogLevel.INFO )


def quantize_standard(
    model_class_name: Literal[ "feature_extraction", "sequence_classification" ],
    src: Path,
    dst: Path,
    model_label: str = "Model",
) -> None:
    """ ‫کوانتایز استاندارد: export + quantize در یک مرحله (سریع‌تر)."""
    dst.mkdir( parents=True, exist_ok=True )

    if ( dst / "model_quantized.onnx" ).exists():
        log_message( LG.RETRIEVAL, f"⏭️  {model_label}: model_quantized.onnx از قبل موجود است — رد شدن", LogLevel.INFO )
        return

    model_cls = MODEL_CLASS_MAP[ model_class_name ]

    log_message( LG.RETRIEVAL, f"🔄 {model_label}: بارگذاری و export به ONNX...", LogLevel.INFO )
    tokenizer = AutoTokenizer.from_pretrained( str( src ) )
    tokenizer.save_pretrained( str( dst ) )

    model = model_cls.from_pretrained( str( src ), export=True )
    model.save_pretrained( str( dst ) )

    log_message( LG.RETRIEVAL, f"⚙️  {model_label}: اعمال Dynamic INT8 Quantization...", LogLevel.INFO )
    quantizer = ORTQuantizer.from_pretrained( model )
    qconfig = AutoQuantizationConfig.avx2( is_static=False, per_channel=False )
    quantizer.quantize( save_dir=str( dst ), quantization_config=qconfig )

    log_message( LG.RETRIEVAL, f"✅ {model_label}: کوانتایزیشن تکمیل شد | {dst}", LogLevel.INFO )


def quantize_low_memory(
    model_class_name: Literal[ "feature_extraction", "sequence_classification" ],
    src: Path,
    dst: Path,
    model_label: str = "Model",
) -> None:
    """ ‫کوانتایز کم‌مصرف: export جدا از quantize (برای مدل‌های بزرگ / RAM کم)."""
    dst.mkdir( parents=True, exist_ok=True )

    # ‫── مرحله ۱: export خام ──
    if not ( dst / "model.onnx" ).exists():
        log_message( LG.RETRIEVAL, f"🔄 {model_label}: export به ONNX (حالت low-memory)...", LogLevel.INFO )
        tokenizer = AutoTokenizer.from_pretrained( str( src ) )
        tokenizer.save_pretrained( str( dst ) )

        model_cls = MODEL_CLASS_MAP[ model_class_name ]
        model = model_cls.from_pretrained( str( src ), export=True )
        model.save_pretrained( str( dst ) )

        del model
        _free_memory()
        log_message( LG.RETRIEVAL, f"✅ {model_label}: export تمام شد — RAM آزاد شد", LogLevel.INFO )
    else:
        log_message( LG.RETRIEVAL, f"⏭️  {model_label}: model.onnx موجود است، رد شدن از export...", LogLevel.INFO )

    # ‫── مرحله ۲: quantize روی فایل ذخیره‌شده ──
    if not ( dst / "model_quantized.onnx" ).exists():
        log_message( LG.RETRIEVAL, f"⚙️  {model_label}: اعمال INT8 Quantization...", LogLevel.INFO )
        quantizer = ORTQuantizer.from_pretrained( str( dst ) )
        qconfig = AutoQuantizationConfig.avx2( is_static=False, per_channel=False )
        quantizer.quantize( save_dir=str( dst ), quantization_config=qconfig )
        log_message( LG.RETRIEVAL, f"✅ {model_label}: کوانتایزیشن تمام شد | {dst}", LogLevel.INFO )
    else:
        log_message( LG.RETRIEVAL, f"⏭️  {model_label}: model_quantized.onnx موجود است.", LogLevel.INFO )


def quantize_model(
    model_class_name: Literal[ "feature_extraction", "sequence_classification" ],
    src: Path,
    dst: Path,
    *,
    low_memory: bool = False,
    model_label: str = "Model",
) -> None:
    """‫ ‫تابع ورودی واحد: انتخاب خودکار بین standard و  ‫‫low-memory."""
    if low_memory:
        quantize_low_memory( model_class_name, src, dst, model_label )
    else:
        quantize_standard( model_class_name, src, dst, model_label )


def quantize_from_settings( low_memory_reranker: bool = True ) -> None:
    """ ‫اجرای کوانتایز برای مدل‌های تعریف‌شده در settings.py پروژه."""
    try:
        from src.config.settings import get_settings
    except ImportError as exc:
        log_message( LG.RETRIEVAL, "❌ نمی‌توان settings.py را import کرد. "
                     "مطمئن شوید که در ریشه‌ی پروژه هستید یا PYTHONPATH تنظیم شده است.", LogLevel.ERROR )
        raise SystemExit( 1 ) from exc

    settings = get_settings()
    settings.ONNX_EMBEDDING_PATH.mkdir( parents=True, exist_ok=True )
    settings.ONNX_RERANKER_PATH.mkdir( parents=True, exist_ok=True )

    #‫ Embedding (حالت استاندارد — معمولاً سبک‌تر است)
    quantize_model(
        model_class_name="feature_extraction",
        src=settings.EMBEDDING_MODEL_PATH,
        dst=settings.ONNX_EMBEDDING_PATH,
        low_memory=False,
        model_label="E5 Embedding",
    )

    #‫ ‫Reranker (حالت low-memory در صورت درخواست)
    quantize_model(
        model_class_name="sequence_classification",
        src=settings.RERANKER_MODEL_PATH,
        dst=settings.ONNX_RERANKER_PATH,
        low_memory=low_memory_reranker,
        model_label="Reranker",
    )

    log_message( LG.RETRIEVAL, "🎉 تبدیل و کوانتایزیشن هر دو مدل با موفقیت پایان یافت.", LogLevel.INFO )
