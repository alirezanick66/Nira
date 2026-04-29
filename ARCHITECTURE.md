# 🏗️ معماری فنی

## 🔄 جریان درخواست (Request Flow)

```text
User Input (Farsi)
      │
      ▼
🧩 NLU Pipeline (Rule/Config-Based)
  ├─ PersianNormalizer + PersianNumberConverter
  ├─ Intent Detector (greeting → refine → search → compare)
  ├─ Slot Filler (Price, Brand, RAM, Storage via domain_knowledge.json)
  └─ ConflictResolver (حذف خودکار فیلترهای متناقض + تولید warnings)
      │
      ▼
🔍 Hybrid Retrieval (Qdrant)
  ├─ Dense Vector (E5) + Sparse Vector (BM25)
  ├─ Metadata Filters (price, brand, ram_gb, tags, etc.)
  ├─ Fusion: RRF (Reciprocal Rank Fusion)
  └─ 🔄 Smart Fallback: حذف تدریجی فیلترها در صورت 0 نتیجه
      │
      ▼
⚖️ Reranker Service
  └─ Cross-Encoder (bge-reranker-v2-m3 | ONNX INT8) → Top 3
      │
      ▼
💬 LLM Orchestrator + Memory
  ├─ ConversationMemory (Sliding Window max=3)
  ├─ Intent: refine → تزریق تاریخچه به Context
  ├─ Groq (Primary) → Gemini (Fallback) → JSON Mode
  └─ Pydantic Validation + Deterministic Fallback
      │
      ▼
✅ Standardized JSON Response → Client (FastAPI `/api/v1/search`)
├─ احراز هویت: `X-API-Key` Middleware
├─ Frontend: Typewriter + Quick Actions + Session Persistence
└─ B2B: Structured `SearchResponse` + Rate Limiting
```

---

## 🧩 مؤلفه‌های اصلی

|         لایه         |                      مسئولیت                      |                                                   پیاده‌سازی فعلی                                                    |
| :------------------: | :-----------------------------------------------: | :------------------------------------------------------------------------------------------------------------------: |
|   **NLU Pipeline**   | نرمال‌سازی، تشخیص نیت، استخراج اسلات، مدیریت تضاد | `NLUPipeline` + `domain_knowledge.json` + `ConflictResolver` (اولویت `price > brand > specs` + پشتیبانی `brand_not`) |
|    **Retrieval**     |   جستجوی ترکیبی و فیلتربرداری هوشمند در Qdrant    |          `QdrantHybridRetriever` (Dense + Sparse + RRF + پشتیبانی صریح از `must_not` برای حذف برندها/تگ‌ها)          |
|     **Reranker**     |               مرتب‌سازی نهایی دقیق                |                          `RerankerService` (Cross-Encoder، Batch Inference، ONNX INT8 فعال)                          |
| **LLM Orchestrator** |              تولید پاسخ ساختاریافته               |               `LLMOrchestrator` (Groq→Gemini Fallback + `response_format=json` + Pydantic Validation)                |
|      **Memory**      |               مدیریت Context مکالمه               |                    `ConversationMemory` (Sliding Window `max=3`، Session-based UUID، Thread-Safe)                    |
|     **Frontend**     |              رابط کاربری دمو و تعامل              |          `Vanilla HTML/CSS/JS` سرو شده توسط FastAPI، `localStorage` Session، تم‌دهی پویا، Typewriter Effect          |


## 📂 ساختار پروژه (Project Structure)

```text
├── .env
├── .gitignore
├── .style.yapf
├── ARCHITECTURE.md           # مستندات معماری پروژه
├── FRONT_README.md           # راهنمای رابط کاربری
├── INSTRUCTIONS.md           # دستورالعمل‌های توسعه و نصب
├── README.md                 # معرفی کلی پروژه
├── ROADMAP.md                # نقشهٔ راه و برنامه‌های آینده
├── alembic/                  # مدیریت مایگریشن‌های دیتابیس
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 7e357f5fe430_add_sync_progress_table.py
│       └── b595023ef435_init_product_raw_cache_table.py
├── alembic.ini               # تنظیمات اتصال و پیکربندی Alembic
├── data/                     # لاگ‌ها و دیتای تست
│   └── logs/
│       ├── api.log
│       ├── database.log
│       ├── dataprocessing.log
│       ├── llm.log
│       ├── nlu.log
│       └── retrieval.log
├── frontend/                 # رابط کاربری دمو (Vanilla JS)
│   ├── index.html
│   ├── script.js
│   └── style.css
├── models/                   # مدل‌های هوشمند (FP32 & ONNX INT8)
│   └── onnx/
│       ├── e5-opt-int8/      # مدل Embedding بهینه‌شده
│       └── reranker-opt-int8/ # مدل Reranker بهینه‌شده
├── pyproject.toml            # مدیریت وابستگی‌ها و تنظیمات ابزارها
├── scripts/                  # اسکریپت‌های تست و سناریوهای یکپارچه
│   ├── index_qdrant.py
│   ├── quantize_unified.py
│   └── sync_test.py
├── src/                      # سورس‌کد اصلی (ماژولار)
│   ├── api/                  # لایهٔ وب: FastAPI، Schemas، Dependencies
│   │   ├── dependencies.py
│   │   ├── main.py
│   │   └── schemas.py
│   ├── config/               # تنظیمات، لاگینگ، دانش دامنه (JSON)
│   │   ├── domain_knowledge.json
│   │   ├── knowledge_loader.py
│   │   ├── logging_config.py
│   │   └── settings.py
│   ├── core/                 # هستهٔ هوش مصنوعی
│   │   ├── llm/              # Orchestrator، Clients، Memory، Prompts
│   │   │   ├── clients.py
│   │   │   ├── memory.py
│   │   │   ├── orchestrator.py
│   │   │   ├── prompts.py
│   │   │   └── schemas.py
│   │   ├── nlu/              # Pipeline، Normalizer، Schemas
│   │   │   ├── conflict_resolver.py
│   │   │   ├── model_masker.py
│   │   │   ├── nlu_pipeline.py
│   │   │   ├── normalizer.py
│   │   │   ├── number_converter.py
│   │   │   ├── schemas.py
│   │   │   └── slot_extractor.py
│   │   ├── progress_tracker.py
│   │   ├── resilience/       # مدیریت خطا و Retry APIها
│   │   │   └── api_resilience.py
│   │   └── vector/           # Qdrant Indexer، Payload، Retriever
│   │       ├── qdrant_indexer.py
│   │       ├── qdrant_payload.py
│   │       └── qdrant_retriever.py
│   ├── data/                 # لایهٔ داده: Fetchers، Models، Repositories، Transformers
│   │   ├── db/
│   │   │   ├── engine.py
│   │   │   └── models.py
│   │   ├── fetchers/
│   │   │   └── digikala_api.py
│   │   ├── models/
│   │   │   ├── api_responses.py
│   │   │   └── product.py
│   │   ├── processing/
│   │   │   └── product_pipeline.py
│   │   ├── repositories/
│   │   │   └── product_repository.py
│   │   ├── sync/
│   │   │   └── digikala_sync.py
│   │   └── transformers/
│   │       └── product_transformer.py
│   ├── services/             # سرویس‌های مستقل: Embedding، Reranker، Enrichment
│   │   ├── embedding_service.py
│   │   ├── product_enrichment_service.py
│   │   ├── reranker_service.py
│   │   └── sparse_vectorizer.py
│   └── utils/                # ابزارهای کمکی و نرمال‌سازی
│       ├── import_tracker.py
│       ├── spec_normalizer.py
│       └── stracture_project.py
├── test/                     # تست‌های یکپارچه و کیفیت
│   ├── nlu/
│   │   ├── test_integrated_pipeline.py
│   │   ├── test_mvp_refinement.py
│   │   └── test_nlu_pipeline.py
│   └── retrival/
│       ├── test_embedding_quality.py
│       ├── test_full_retrieval_pipeline.py
│       └── test_hybrid_search.py
└── uv.lock                   # قفل نسخهٔ پکیج‌ها
```

---
## ⚙️ تصمیمات طراحی کلیدی (Key Design Decisions)

|                     تصمیم                      |                                                                  دلیل فنی (Rationale)                                                                  |                                                                                                         اثر/مزیت (Impact)                                                                                                          |
| :--------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
|              **حذف RAG/Chunking**              |                       هر محصول = ۱ سند ساختاریافته در Qdrant. Chunking باعث تکه‌تکه شدن متادیتا و کاهش دقت فیلترهای عددی می‌شود.                       |                                                                                   ✅ حفظ یکپارچگی متادیتا، دقت بالاتر در فیلترگذاری، سادگی ایندکس                                                                                   |
|         **استفاده از Rule-Based NLU**          |                 `NLUPipeline` + `domain_knowledge.json` تشخیص نیت را **بدون تأخیر شبکه، بدون هزینه توکن و با دقت قطعی** انجام می‌دهد.                  |                                                                                ✅ کاهش Latency، هزینهٔ صفر توکن برای Intent Detection، پایداری ۱۰۰٪                                                                                 |
|          **پیاده‌سازی Hybrid Search**          | ترکیب `Dense` (درک معنایی) + `Sparse` (تطبیق دقیق کلمات کلیدی) + `RRF` (ادغام رتبه‌ها) بهترین Coverage را برای کوئری‌های محاوره‌ای فارسی فراهم می‌کند. |                                                                                  ✅ پوشش همزمان نیازهای معنایی و کلیدواژه‌ای، کاهش False Negative                                                                                   |
|              **اجبار خروجی JSON**              |     استفاده از `response_format={"type": "json_object"}` + اعتبارسنجی با `pydantic.TypeAdapter`. در صورت شکست، `Deterministic Template` برمی‌گردد.     |                                                                           ✅ تضمین ساختار پاسخ برای کلاینت، جلوگیری از خطای پارسینگ، تجربهٔ کاربری پایدار                                                                           |
| **عدم استفاده از LangChain/LlamaIndex در MVP** |                                             کنترل مستقیم بر لایه‌ها، سربار کمتر، دیباگ آسان‌تر، اصل KISS.                                              |                                                                                           ✅ شفافیت کامل، وابستگی کمتر، سرعت توسعه بالاتر                                                                                           |
|    **بهینه‌سازی ONNX + INT8 Quantization**     |    تبدیل مدل‌های `E5` و `bge-reranker` به ONNX Runtime با کوانتایزیشن Dynamic INT8. تأیید شده با Drift Test (`Cosine: 0.0014`, `Spearman: 1.0000`)     | تبدیل مدل‌های `E5` و `bge-reranker` به ONNX Runtime با کوانتایزیشن Dynamic INT8. تأیید شده با Drift Test (`Cosine: 0.0014`, `Spearman: 1.0000`). \| ✅ کاهش ~۶۰٪ مصرف RAM/CPU، کاهش زمان پاسخ به `<3s`، حفظ دقت در حد نویز محاسباتی |
|     **فرانت‌اند Vanilla + FastAPI Static**     |                                   حذف سربار `npm`/`Vite`/`React` برای فاز دمو. سرو مستقیم `index.html` توسط FastAPI                                    |                                                                          ✅ استقرار تک‌خطی، پایداری بالا، شخصی‌سازی آنی با CSS Variables، تمرکز بر بک‌اند                                                                           |
|      **تزریق وابستگی و مدیریت چرخه حیات**      |                                 جایگزینی کامل الگوی `Singleton` با `FastAPI Lifespan + app.state Dependency Injection`                                 |                                       این تغییر باعث جداسازی کامل نمونه‌سازی از لاجیک تجاری، حذف `State Leakage` در محیط‌های چند-ورکر و امکان `Mock` کردن سرویس‌ها در تست‌های واحد شده است.                                        |
|       **افزودن `X-API-Key` Middleware**        |                                                   جلوگیری از سوءاستفاده از توکن/سرور در مدل B2B/SaaS                                                   |                                                                                  ✅ کنترل دسترسی، ردیابی مصرف هر فروشگاه، آماده‌سازی برای Billing                                                                                   |

---

## 🔌 اصول طراحی Prompt برای چند-دامنه‌ای (Domain-Agnostic Prompts)

برای امکان سوئیچ سریع بین دسته‌بندی‌های مختلف (موبایل → هدفون → لپ‌تاپ) بدون تغییر کد:

- ✅ **قالب‌های پارامتریک**: استفاده از `{domain_topic}`, `{key_attributes}`, `{price_ranges}` در System Prompt
- ✅ **جداسازی دانش دامنه**: تمام مقادیر خاص دامنه در `domain_knowledge.json` نگهداری شود، نه در کد پرامپت
- ✅ **Slot Injection در Runtime**: `PromptEngine` مقادیر را از `KnowledgeCache` خوانده و در قالب تزریق می‌کند
- ✅ **Fallback به قالب عمومی**: اگر دامنهٔ جدید تعریف نشده بود، از قالب عمومی با فیلترهای پایه استفاده شود

**مثال:**
```text
System: "تو دستیار خرید {domain_topic} هستی. معیارهای کلیدی: {key_attributes}. رنج‌های قیمتی: {price_ranges}..."
```

---

## 🔮 الگوهای معماری برای مقیاس‌پذیری (Post-MVP Patterns)

این بخش الگوهای پیشنهادی برای فیچرهای آینده را بدون تعهد به زمان‌بندی مشخص می‌کند:

### 🧠 لایهٔ هوش و شخصی‌سازی

|                  فیچر                  |             الگوی پیاده‌سازی پیشنهادی             |                  وابستگی‌ها                   |                    ریسک تغییر تکنولوژی                     |
| :------------------------------------: | :-----------------------------------------------: | :-------------------------------------------: | :--------------------------------------------------------: |
| **پرفروش‌ترین/تخفیف‌دار/شمارش معکوس**  |       Tool Calling + Cache لایه‌ای (Redis)        |         Sync لحظه‌ای قیمت از فروشگاه          |              🔵 کم (ابزار استاندارد FastAPI)               |
|  **Personalization + تاریخچه سلیقه**   |   User Profile Service + Vector Memory per User   | Auth + PostgreSQL + Qdrant Collection جداگانه |   🟡 متوسط (اگر کاربر >100K، نیاز به بهینه‌سازی برداری)    |
| **بازخورد Like/Dislike + یادگیری سبک** | Event-Driven Pipeline + Lightweight Ranking Model |      Analytics DB + Feedback Aggregator       |             🔵 کم (الگوی استاندارد RLHF-lite)              |

### 🛒 لایهٔ یکپارچه‌سازی فروشگاه

|             فیچر              |       الگوی پیاده‌سازی پیشنهادی       |             وابستگی‌ها              |                    ریسک تغییر                    |
| :---------------------------: | :-----------------------------------: | :---------------------------------: | :----------------------------------------------: |
| **اتصال سبد خرید / پروفایل**  | OAuth 2.0 + Store API Adapter Pattern |  فروشگاه باید API مستند ارائه دهد   | 🔴 بالا (اگر API ندهد، نیاز به WebView Fallback) |
| **شرایط اقساط + توضیحات مهم** |   Knowledge Base + Rule Engine سبک    | به‌روزرسانی دستی/نیمه‌خودکار قوانین |                      🔵 کم                       |

### 📊 لایهٔ تحلیل و گزارش‌دهی

|                       فیچر                        |                الگوی پیاده‌سازی پیشنهادی                 |               وابستگی‌ها               | ریسک تغییر |
| :-----------------------------------------------: | :------------------------------------------------------: | :------------------------------------: | :--------: |
| **لاگ خودکار Intent/Slot + کوئری‌های بدون نتیجه** | Structured Logging → Analytics DB (ClickHouse/Timescale) | Pipeline جمع‌آوری لاگ + Dashboard ساده |   🔵 کم    |
| **گزارش هفتگی «نیازهای پرجستجو» / «شکاف موجودی»** |    Scheduled Job + Template Engine → Email/Dashboard     |      دسترسی به داده‌های تجمیع‌شده      |   🔵 کم    |

---

## ⚠️ Watchlist: نقاط با ریسک تغییر تکنولوژی

|                       نقطه                       |               وضعیت فعلی                |                               ریسک آینده                               |                              راه‌حل پیشنهادی                               |
| :----------------------------------------------: | :-------------------------------------: | :--------------------------------------------------------------------: | :------------------------------------------------------------------------: |
|           **شخصی‌سازی در مقیاس بزرگ**            |              ❌ پیاده‌نشده               | 🟡 اگر کاربران فعال >100,000 شوند، Vector Memory per User سنگین می‌شود |           جداسازی Collection کاربران در Qdrant + Sharding هوشمند           |
|    **Knowledge Graph + استدلال چندمرحله‌ای**     | ❌ فعلاً با Rule Engine پوشش داده می‌شود |   🟡 اگر نیاز به استنتاج پیچیده‌تر پیدا شود، قواعد دستی کافی نیستند    |              ارزیابی Neo4j + Graph RAG فقط در صورت نیاز واقعی              |

---

## 📊 ارزیابی، پایش و بازخورد (Evaluation & Monitoring)

### معیارهای سنجش دوره‌ای

- 🎯 **`Faithfulness`**: عدم تناقض پاسخ LLM با متادیتای واقعی محصول
- 🔍 **`Context Precision`**: کیفیت و ارتباط داده‌های بازیابی‌شده با کوئری کاربر
- 💬 **`Answer Relevancy`**: پاسخ‌دهی دقیق به نیاز واقعی (نه فقط تطبیق کلیدواژه)
- ⏱️ **`Latency`**: `<3 s` برای کل چرخه (NLU → Retrieval → Rerank → LLM)

### حلقه بازخورد و آنالیتیکس

- 📊 **Light Analytics**: ثبت `query → intent → applied_filters → zero_results_count` برای بهینه‌سازی `domain_knowledge.json`
- 🛠️ **Feedback Loop**: گزارش خودکار کوئری‌های `0 نتیجه` برای اضافه کردن قواعد جدید یا به‌روزرسانی آستانه‌ها
- 📦 **Dashboard (آینده)**: نمایش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «نرخ تبدیل پیشنهاد»

### ابزارهای پیشنهادی برای ارزیابی

- 🔹 **RAGAS** یا **DeepEval** برای سنجش خودکار کیفیت پاسخ‌ها
- 🔹 **Logging ساختاریافته** با `src/config/logging_config.py` برای ردیابی خطاها
- 🔹 **Semantic Cache Hit-Rate** برای اندازه‌گیری کارایی کش کوئری‌های تکراری
- `validate_quantization_drift.py` برای پایش دوره‌ای افت دقت مدل‌های ONNX