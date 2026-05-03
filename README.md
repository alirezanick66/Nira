# 🧠 Nira

## 📖 نمای کلی

نیرا یک دستیار هوشمند خرید مبتنی بر **AI** است که به کاربران کمک می‌کند بر اساس نیاز واقعی خود، بهترین محصول را انتخاب کنند. 
🎯 **تمرکز اصلی:** `Pre-Search Decision Making` (تصمیم‌گیری هوشمند قبل از انتخاب محصول)

## ❗ مسئله و راه‌حل

**مشکل:** کاربران در انتخاب محصول دچار سردرگمی هستند، فیلترهای فروشگاه‌ها پیچیده و ناکارآمدند، و فروشگاه‌ها به جای چت‌بات عمومی، **افزایش نرخ تبدیل** و **کاهش هزینه پشتیبانی** می‌خواهند. 📉

**راه‌حل:**

1. درک نیاز کاربر از طریق زبان طبیعی محاوره‌ای فارسی
2. تبدیل خودکار نیاز به فیلترهای دقیق و قابل اجرا (`Qdrant` + `Metadata`)
3. ارائه حداکثر ۲ پیشنهاد هدفمند + توضیح شفاف «چرا این محصول؟» 🎯

## 📈 ارزش پیشنهادی

|🏢 برای فروشگاه‌ها|👤 برای کاربر|
|:--|:--|
|افزایش نرخ تبدیل خرید|کاهش سردرگمی در انتخاب|
|کاهش زمان تصمیم‌گیری کاربر|صرفه‌جویی در زمان|
|کاهش فشار روی تیم پشتیبانی|تصمیم‌گیری با اعتماد بیشتر|

## 🎯 محدوده پروژه (Scope)

✅ **شامل MVP:**

- فیلترگذاری خودکار از روی متن کاربر (Token-Based NLU)
- جستجوی ترکیبی (`Hybrid Search + RRF`) بدون Chunking
- توضیح شفاف دلیل پیشنهاد (`Explainability` با LLM)
- قابلیت اصلاح سریع فیلتر («نه، ارزون‌تر/سبک‌تر») بدون ریست چت (`Conversation Memory`)
- بهینه‌سازی جهت مصرف کمترین `Token`
- پیشنهاد محصول هوشمند (موبایل، هدفون/هندزفری)
- `Smart Fallback` خودکار (حذف تدریجی فیلترهای سخت در صورت صفر نتیجه)
- پشتیبانی از `Intent: refine` متصل به حافظه مکالمه

❌ **خارج از محدوده MVP:**

- Personalization پیشرفته، Multi-Agent
- پیگیری/لغو سفارش، مرجوعی، پشتیبانی پس از خرید
- گراف دانش (Knowledge Graph) یا Fine-tuning سنگین

## 📦 دسته‌بندی اولیه (MVP)

- 📱 موبایل
- 🎧 هدفون / هندزفری

## 🛠️ Tech Stack

- **Backend:** `FastAPI` + `Uvicorn` (Python 3.11+) + `SSE` (Real-time UX)
- **Vector DB:** `Qdrant` (Hybrid: Dense E5 + Sparse BM25 + RRF)
- **Relational DB:** `PostgreSQL` (Async Logging, Raw Cache, Analytics) + `Alembic` (Migrations)
- **Embedding:** `intfloat/multilingual-e5-base` (768-dim)
- **Reranker:** `BAAI/bge-reranker-v2-m3` (Cross-Encoder)
- **LLM:** `Groq` (Primary) + `Gemini` (Fallback) | `JSON Mode` + `Pydantic`
- **Package Manager:** `uv`
- **Inference Optimization:** `ONNX` Runtime + `INT8` Quantization

## 🚀 Quick Start

```bash
# ‫1. تنظیم محیط مجازی و نصب وابستگی‌ها
uv sync

# ‫2. کپی و تنظیم متغیرهای محیطی (ضروری)
cp .env.example .env
# ‫⚠️ فایل .env را باز کنید و GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY را تنظیم نمایید.

# ‫3. اعمال ساختار جداول دیتابیس
uv run alembic upgrade head

# ‫4. اجرای سرور
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# ‫5. دسترسی به دمو و مستندات تعاملی
http://localhost:8000/
http://localhost:8000/docs
```

## 📊 وضعیت پیاده‌سازی

برای ماتریس دقیق پیشرفت، فازهای تکمیل‌شده و نقشه راه، به [ROADMAP.md]( ROADMAP) مراجعه کنید.

---

**نسخه:** 1.0.0  **آخرین به‌روزرسانی:** 2026/05/03