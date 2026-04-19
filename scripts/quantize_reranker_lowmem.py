# scripts/quantize_reranker_lowmem.py
"""کوانتایزیشن Reranker با مصرف RAM کمتر"""
import gc
import torch
from pathlib import Path
from transformers import AutoTokenizer
from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from src.config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    src = settings.RERANKER_MODEL_PATH
    dst = settings.ONNX_RERANKER_PATH
    dst.mkdir( parents=True, exist_ok=True )

    # ── مرحله ۱: فقط export به ONNX (بدون quantize) ──
    if not ( dst / "model.onnx" ).exists():
        print( "🔄 Export به ONNX..." )
        tokenizer = AutoTokenizer.from_pretrained( str( src ) )
        tokenizer.save_pretrained( str( dst ) )

        model = ORTModelForSequenceClassification.from_pretrained( str( src ), export=True )
        model.save_pretrained( str( dst ) )

        # ✅ آزادسازی RAM قبل از quantize
        del model
        gc.collect()
        torch.cuda.empty_cache()
        print( "✅ Export تمام شد — RAM آزاد شد" )
    else:
        print( "⏭️ model.onnx موجود است، رد شدن از export..." )

    # ── مرحله ۲: quantize روی فایل ذخیره‌شده ──
    if not ( dst / "model_quantized.onnx" ).exists():
        print( "⚙️ اعمال INT8 Quantization..." )
        quantizer = ORTQuantizer.from_pretrained( str( dst ) )
        qconfig = AutoQuantizationConfig.avx2( is_static=False, per_channel=False )
        quantizer.quantize( save_dir=str( dst ), quantization_config=qconfig )
        print( f"✅ کوانتایزیشن تمام شد | {dst}" )
    else:
        print( "⏭️ model_quantized.onnx موجود است." )
