"""اسکریپت تبدیل و کوانتایز کردن مدل‌ها به ONNX (Dynamic INT8)
‫مسئول: بارگذاری مدل‌های PyTorch، اکسپورت به ONNX، اعمال کوانتایزیشن و ذخیرهٔ خروجی
"""
from pathlib import Path
import logging
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForFeatureExtraction, ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from src.config.settings import get_settings

logging.basicConfig( level="INFO", format="%(levelname)s | %(message)s" )


def _quantize_model(
    model_class: type[ ORTModelForFeatureExtraction | ORTModelForSequenceClassification ],
    model_id: Path,
    out_path: Path,
    model_name: str,
) -> None:
    if out_path.exists() and ( out_path / "model_quantized.onnx" ).exists():
        logging.info( f"✅ مدل {model_name} از قبل در {out_path} کوانتایز شده است. در حال رد شدن..." )
        return

    logging.info( f"🔄 بارگذاری و اکسپورت {model_name}..." )
    tokenizer = AutoTokenizer.from_pretrained( str( model_id ) )
    tokenizer.save_pretrained( str( out_path ) )

    model = model_class.from_pretrained( str( model_id ), export=True )
    model.save_pretrained( str( out_path ) )

    logging.info( f"⚙️ اعمال Dynamic INT8 Quantization روی {model_name}..." )
    quantizer = ORTQuantizer.from_pretrained( model )
    qconfig = AutoQuantizationConfig.avx2( is_static=False, per_channel=False )
    quantizer.quantize( save_dir=str( out_path ), quantization_config=qconfig )
    logging.info( f"✅ کوانتایزیشن {model_name} تکمیل شد | مسیر: {out_path}" )


if __name__ == "__main__":
    settings = get_settings()
    settings.ONNX_EMBEDDING_PATH.mkdir( parents=True, exist_ok=True )
    settings.ONNX_RERANKER_PATH.mkdir( parents=True, exist_ok=True )

    _quantize_model( ORTModelForFeatureExtraction, settings.EMBEDDING_MODEL_PATH, settings.ONNX_EMBEDDING_PATH, "E5" )
    _quantize_model( ORTModelForSequenceClassification, settings.RERANKER_MODEL_PATH, settings.ONNX_RERANKER_PATH, "Reranker" )
    logging.info( "🎉 تبدیل و کوانتایزیشن هر دو مدل با موفقیت پایان یافت." )
