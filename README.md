# 🧠 Nira

## 📖 نمای کلی

نیرا یک دستیار هوشمند خرید مبتنی بر **AI** است که به کاربران کمک می‌کند بر اساس نیاز واقعی خود، بهترین محصول را انتخاب کنند. 
🎯 **تمرکز اصلی:** `Pre-Search Decision Making` (تصمیم‌گیری هوشمند قبل از انتخاب محصول)

## ❗ مسئله و راه‌حل

**مشکل:** کاربران در انتخاب محصول دچار سردرگمی هستند، فیلترهای فروشگاه‌ها پیچیده و ناکارآمدند، و فروشگاه‌ها به جای چت‌بات عمومی، **افزایش نرخ تبدیل** و **کاهش هزینه پشتیبانی** می‌خواهند. 📉

**راه‌حل:**
- درک نیاز کاربر از طریق زبان طبیعی محاوره‌ای فارسی
- استخراج هوشمند نیت و فیلترها مستقیماً توسط LLM + اعتبارسنجی سخت‌گیرانه Pydantic
- تبدیل خودکار نیاز به فیلترهای دقیق و قابل اجرا (`Qdrant` + `Metadata`)
- ارائه حداکثر ۲ پیشنهاد هدفمند + توضیح شفاف «چرا این محصول؟» 🎯

## 📈 ارزش پیشنهادی

|🏢 برای فروشگاه‌ها|👤 برای کاربر|
|:--|:--|
|افزایش نرخ تبدیل خرید|کاهش سردرگمی در انتخاب|
|کاهش زمان تصمیم‌گیری کاربر|صرفه‌جویی در زمان|
|کاهش فشار روی تیم پشتیبانی|تصمیم‌گیری با اعتماد بیشتر|

## 🎯 محدوده پروژه (Scope)

✅ **شامل MVP:**

-  استخراج نیت و فیلتر مبتنی بر LLM تشخیص دقیق نیاز با درک معنایی پیشرفته، بدون وابستگی به قواعد ثابت + Fast-Path برای احوال‌پرسی (تشخیص آنی بدون مصرف توکن)
- 🔍 جستجوی ترکیبی (Hybrid Search + RRF) بدون Chunking + فیلترگذاری هوشمند متادیتا
- 💬 توضیح شفاف دلیل پیشنهاد (Explainability) با LLM و خروجی ساختاریافته JSON
- 🔄 Refine هوشمند (Context-Aware): ادغام پویای فیلترهای جدید با تاریخچه مکالمه توسط LLM و حفظ کامل زمینه (بدون لاجیک Merge در پایتون)
- 🏷️ درک ذاتی نام برندها: نرمال‌سازی خودکار مترادف‌ها و تایپوها توسط مدل زبانی با تزریق اسکیما
- ⚡ بهینه‌سازی جهت مصرف کمترین Token و تأخیر زیر ۳ ثانیه (ONNX INT8)
- 🛡️ Smart Fallback خودکار: حذف تدریجی فیلترهای سخت در صورت صفر نتیجه برای حفظ تجربه کاربری
- 🖼️ خط لوله غنی‌سازی مدیا: واکشی پویا تصاویر از دیتابیس و مدیریت URLها بدون سربار در جستجو
- پیشنهاد محصول هوشمند (موبایل، هدفون/هندزفری)

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
- **LLM:** `Groq` (Primary) + `Gemini` (Fallback) | `JSON Mode` + `Pydantic`+ Cache: `AsyncTTLCache` (In-Memory, TTL-configurable)
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
## 📄 License

This project is licensed under the MIT License.

⚠️ Attribution is required. Any usage must credit the original author and link to this repository.

---
## ⚠️ Disclaimer

This project is for educational and informational purposes only.

It does NOT provide legal advice and should not be used as a substitute for professional legal consultation.

The author assumes no responsibility for any decisions made based on the system’s outputs.

---

**نسخه:** 2.1.0  **آخرین به‌روزرسانی:** 2026/08/22
