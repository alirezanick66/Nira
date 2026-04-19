"""سنجش دقیق افت دقت پس از کوانتایزیشن INT8 (FP32 Baseline vs INT8 Quantized)"""
import os
import shutil
import numpy as np
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from src.config.settings import get_settings

# ────────────── داده‌های تست نماینده (کوئری + داکیومنت واقعی) ──────────────
TEST_PAIRS = [
    ( "گوشی با دوربین خوب و باتری قوی", "گوشی موبایل شیائومی ردمی نوت 13 با باتری 5000 و دوربین 108 مگاپیکسل" ),
    ( "ارزان ترین گوشی شیائومی", "آیفون 15 پرومکس با قیمت بالا و کیفیت ساخت عالی" ),
    ( "گوشی سبک برای بازی", "گوشی گیمینگ ایسوس ROG Phone 8 با رم 16 گیگ و خنک‌کننده" ),
]

# ────────────── فایل‌هایی که باید از مدل اصلی به پوشه ONNX کپی شوند ──────────────
REQUIRED_CONFIG_FILES = [
    "config.json",
    "tokenizer_config.json",
    "tokenizer.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",          # برای E5 multilingual
]


def make_path_safe( local_path: str | Path ) -> str:
    """تبدیل مسیر به فرمتی که HuggingFace آن را با مدل‌های آنلاین اشتباه نگیرد"""
    abs_path = Path( local_path ).resolve()
    try:
        rel_path = os.path.relpath( abs_path, Path.cwd() )
        safe_str = "./" + rel_path.replace( "\\", "/" )
    except ValueError:
        safe_str = abs_path.as_posix()
    return safe_str


def ensure_onnx_configs( source_model_path: Path, onnx_path: Path ) -> None:
    """
    کپی فایل‌های کانفیگ ضروری از مدل اصلی به پوشه ONNX در صورت نبودن.
    بدون این فایل‌ها Optimum و Tokenizer لود نمی‌شوند.
    """
    for filename in REQUIRED_CONFIG_FILES:
        src = source_model_path / filename
        dst = onnx_path / filename
        if src.exists() and not dst.exists():
            shutil.copy2( src, dst )
            print( f"  📋 کپی شد: {filename} → {onnx_path.name}/" )
        elif not src.exists() and not dst.exists():
            # فایل‌های اختیاری مثل sentencepiece ممکنه نباشند — فقط config.json حیاتیه
            if filename == "config.json":
                raise FileNotFoundError( f"فایل حیاتی {filename} نه در مدل اصلی ({source_model_path}) "
                                         f"و نه در پوشه ONNX ({onnx_path}) یافت شد." )


def cosine_sim( a: np.ndarray, b: np.ndarray ) -> float:
    return float( np.dot( a, b ) / ( np.linalg.norm( a ) * np.linalg.norm( b ) + 1e-9 ) )


def mean_pool( last_hidden: np.ndarray, attention_mask: np.ndarray ) -> np.ndarray:
    """Mean pooling با mask صحیح — مستقل از shape مشکل‌دار broadcast"""
    mask_expanded = attention_mask[..., None ].astype( np.float32 )          # (B, T, 1)
    sum_hidden = np.sum( last_hidden * mask_expanded, axis=1 )          # (B, D)
    sum_mask = np.sum( attention_mask, axis=1, keepdims=True ).astype( np.float32 )          # (B, 1)
    return sum_hidden / ( sum_mask + 1e-9 )


def test_embedding_drift() -> float:
    print( "🔍 سنجش Drift مدل Embedding..." )
    settings = get_settings()

    onnx_path = Path( settings.ONNX_EMBEDDING_PATH )
    source_path = Path( settings.EMBEDDING_MODEL_PATH )

    # ✅ کپی خودکار فایل‌های کانفیگ در صورت نیاز
    ensure_onnx_configs( source_path, onnx_path )

    fp32_model = SentenceTransformer( str( source_path ) )

    from optimum.onnxruntime import ORTModelForFeatureExtraction

    onnx_dir = make_path_safe( onnx_path )
    onnx_model = ORTModelForFeatureExtraction.from_pretrained(
        onnx_dir,
        file_name="model_quantized.onnx",
        local_files_only=True,
    )
    tokenizer = AutoTokenizer.from_pretrained( onnx_dir )

    drifts = []
    for q, d in TEST_PAIRS:
        # FP32
        v_q_fp = fp32_model.encode( f"query: {q}", normalize_embeddings=True )
        v_d_fp = fp32_model.encode( f"passage: {d}", normalize_embeddings=True )
        sim_fp = cosine_sim( v_q_fp, v_d_fp )

        # INT8 ONNX
        inputs = tokenizer(
            [ f"query: {q}", f"passage: {d}" ],
            padding=True,
            truncation=True,
            return_tensors="np",
        )
        outputs = onnx_model( **inputs )

        # ✅ اصلاح: pooling صحیح + unpack صریح
        pooled = mean_pool( outputs.last_hidden_state, inputs[ "attention_mask" ] )
        norms = np.linalg.norm( pooled, axis=1, keepdims=True )
        normalized = pooled / ( norms + 1e-9 )
        v_q_onnx = normalized[ 0 ]
        v_d_onnx = normalized[ 1 ]

        sim_onnx = cosine_sim( v_q_onnx, v_d_onnx )
        drifts.append( abs( sim_fp - sim_onnx ) )

    avg_drift = float( np.mean( drifts ) )
    print( f"📊 میانگین Cosine Drift: {avg_drift:.4f}" )
    return avg_drift


def test_reranker_drift() -> float:
    print( "⚖️ سنجش Drift مدل Reranker..." )
    settings = get_settings()

    source_path = Path( settings.RERANKER_MODEL_PATH )
    onnx_path = Path( settings.ONNX_RERANKER_PATH )

    # ✅ کپی خودکار فایل‌های کانفیگ در صورت نیاز
    ensure_onnx_configs( source_path, onnx_path )

    # مدل اصلی — مسیر مطلق برای PyTorch مشکلی ندارد
    tokenizer = AutoTokenizer.from_pretrained( str( source_path ) )
    fp32_model = AutoModelForSequenceClassification.from_pretrained( str( source_path ) )
    fp32_model.eval()

    # مدل INT8 ONNX
    from optimum.onnxruntime import ORTModelForSequenceClassification

    onnx_dir = make_path_safe( onnx_path )
    onnx_model = ORTModelForSequenceClassification.from_pretrained(
        onnx_dir,
        file_name="model_quantized.onnx",
        local_files_only=True,
    )

    queries = [ q for q, _ in TEST_PAIRS ]
    docs = [ d for _, d in TEST_PAIRS ]

    inputs_pt = tokenizer( queries, docs, padding=True, truncation=True, max_length=256, return_tensors="pt" )
    with torch.inference_mode():
        logits_fp32 = fp32_model( **inputs_pt ).logits.squeeze( -1 )
        fp32_scores = torch.sigmoid( logits_fp32 ).numpy()

    inputs_np = tokenizer( queries, docs, padding=True, truncation=True, max_length=256, return_tensors="np" )
    onnx_outputs = onnx_model( **inputs_np )
    logits_onnx = onnx_outputs.logits.squeeze( -1 )
    onnx_scores = 1.0 / ( 1.0 + np.exp( -logits_onnx ) )

    from scipy.stats import spearmanr
    corr, _ = spearmanr( fp32_scores, onnx_scores )
    print( f"📊 Spearman Correlation: {corr:.4f}" )
    return float( corr )


if __name__ == "__main__":
    import gc
    try:

        # ── تست اول ──
        emb_drift = test_embedding_drift()
        gc.collect()          # ✅ آزادسازی RAM بین دو تست

        # ── تست دوم ──
        rerank_corr = test_reranker_drift()

        print( "\n" + "=" * 30 )
        if emb_drift < 0.04 and rerank_corr > 0.95:
            print( "✅ تست با موفقیت پاس شد." )
        else:
            print( "⚠️ هشدار: کیفیت مدل کوانتایز شده پایین است." )
        print( "=" * 30 )

    except Exception as exc:
        print( f"\n❌ خطای نهایی: {exc}" )
        print( "💡 نکته: مطمئن شوید فایل config.json مدل اصلی را در پوشه ONNX کپی کرده‌اید." )
