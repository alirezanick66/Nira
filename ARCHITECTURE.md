# 🏗️ معماری فنی

# 🔄 جریان درخواست (Request Flow)

```text
User Input (Farsi)
      │
      ▼
⚡ Fast-Path Greeting Check (Rule-Based, <1ms)
├─ اگر مچ شد → پاسخ فوری از کانفیگ → پایان (بدون مصرف توکن)
└─ اگر مچ نشد → ادامه به مرحله بعد
      │
      ▼

⚡ Semantic Cache Check (Extract Layer)

├─ اگر Hit → بازگشت فیلترهای کش‌شده → ادامه به Retrieval

└─ اگر Miss → ادامه به LLM Extract
      │
    ▼
🧠 LLM Extract Engine (Call 1)
├─ PersianNormalizer + تزریق تاریخچه ($history)
├─ تزریق فیلترهای قبلی ($last_filters) + محصولات قبلی ($last_products)
├─ تزریق پویای راهنمای دامنه ($domain_schema)
├─ فراخوانی Groq → Gemini (Fallback)
└─ اعتبارسنجی سخت‌گیرانه Pydantic (LLMExtractSchema)
      │
      ▼
🚦 مدیریت Intent و فیلترها
├─ general_chat → پاسخ کوتاه → پایان
├─ needs_clarification=True → پرسش شفاف‌ساز → پایان
└─ search/refine/compare → استخراج نهایی:
   ├─ semantic_query (بهینه‌شده برای Embedding)
   ├─ metadata_filters (ادغام‌شده توسط LLM برای refine)
   └─ has_conflict / clarification (لاگ و مدیریت)
      │
      ▼
🔍 Hybrid Retrieval (Qdrant)
├─ Dense Vector (E5) + Sparse Vector (BM25)
├─ اعمال Metadata Filters نهایی
├─ Fusion: RRF (Reciprocal Rank Fusion)
└─ 🔄 Smart Fallback: حذف تدریجی فیلترها در صورت 0 نتیجه
      │
      ▼
⚖️ Reranker Service
└─ Cross-Encoder (bge-reranker-v2-m3 | ONNX INT8) → Top-K نهایی
      │
      ▼
🛍️ Post-Retrieval Enrichment (PostgreSQL)
└─ واکشی غیرمسدودکنندهٔ image_url و جزئیات تکمیلی
      │
      ▼
💬 LLM Generate Engine (Call 2)
├─ PromptEngine (YAML-Driven) با تزریق محصولات و فیلترها
├─ Groq → Gemini (Fallback) → JSON Mode
└─ Pydantic Validation (LLMResponseSchema)
      │
      ▼
✅ Standardized JSON Response → Client
├─ 📦 B2B Contract: `POST /api/v1/search` → JSON
└─ 🌊 UX Stream: `GET /api/v1/search/stream` → SSE
   └─ هسته مشترک: `SearchService` (Protocol-Agnostic)
```

---

## 🧩 مؤلفه‌های اصلی

|             لایه             |                                            مسئولیت                                            |                                          پیاده‌سازی فعلی                                          |
| :--------------------------: | :-------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------: |
|       **Backend Core**       |                      اجرای یکپارچه پایپلاین بدون وابستگی به پروتکل HTTP                       |                       `SearchService` (AsyncIterator مشترک برای POST و SSE)                       |
| **🧠 LLM Extract & Context** | استخراج نیت، فیلترها و `semantic_query` از کوئری محاوره‌ای + مدیریت `refine` با تزریق تاریخچه | `LLMOrchestrator.extract()` + `Fast-Path Greeting` + `Pydantic Validation` + `ConversationMemory` |
|        **Retrieval**         |                         جستجوی ترکیبی و فیلتربرداری هوشمند در Qdrant                          |                  `QdrantHybridRetriever` (Dense + Sparse + RRF + Smart Fallback)                  |
|         **Reranker**         |                                     مرتب‌سازی نهایی دقیق                                      |                   `RerankerService` (Cross-Encoder، Batch Inference، ONNX INT8)                   |
|     **LLM Orchestrator**     |                          تولید پاسخ ساختاریافته و مدیریت Prompt پویا                          |    `LLMOrchestrator` + `PromptEngine` (YAML-Driven، Groq→Gemini Fallback، Pydantic Validation)    |
|        **Enrichment**        |                          واکشی پویا تصاویر و متادیتا پس از رتبه‌بندی                          |                      ProductRepository (Async PostgreSQL + JSONB Extraction)                      |
|          **Memory**          |                        مدیریت Context و ادغام فیلترها (Filter Merging)                        |                    ConversationMemory (Thread-Safe + Applied Filters Storage)                     |
|   **Logging & Telemetry**    |                             ثبت غیرمسدودکننده کوئری‌ها و وضعیت‌ها                             |             `query_log_service.py` (Global Engine + Per-Task AsyncSession، Fail-Safe)             |
|         **Frontend**         |                                    رابط کاربری دمو و تعامل                                    |                      Vanilla ES Modules + SSE + Context-Aware Quick Actions                       |

---

## 📂 ساختار پروژه (Project Structure)

```yaml
├── .env
├── .gitignore
├── .style.yapf
├── ARCHITECTURE.md           # مستندات معماری پروژه
├── FRONT_README.md           # راهنمای رابط کاربری
├── INSTRUCTIONS.md           # دستورالعمل‌های توسعه و نصب
├── PRODUCT.md                # تحلیل محصول و رفتار کاربر
├── README.md                 # معرفی کلی پروژه
├── ROADMAP.md                # نقشهٔ راه و برنامه‌های آینده
├── alembic/                  # مدیریت مایگریشن‌های دیتابیس
│   ├── README
│   ├── env.py
│   ├── script.py.mako
│   └── versions/             # فایل‌های مهاجرت (query_logs, sync_progress, raw_cache)
├── alembic.ini               # تنظیمات اتصال و پیکربندی Alembic
├── data/                     # لاگ‌ها و داده‌های محلی
│   └── logs/                 # لاگ‌های تفکیک‌شده (api, database, llm, retrieval, dataprocessing)
├── frontend/                 # رابط کاربری دمو
│   ├── css/                  # توکن‌ها، چیدمان، کامپوننت‌ها و استایل اصلی
│   ├── js/                   # لایه‌های ارتباط، جلسه و رندر DOM
│   │── admin.html       #صفحه داشبورد کوئری ها
│   ├── index.html
│   └── script.js             # نقطه ورود اصلی فرانت‌اند
├── models/                   # مدل‌های هوشمند (FP32 & ONNX INT8)
│   └── onnx/                 # e5-opt-int8 و reranker-opt-int8 (همراه با کانفیگ و توکنایزر)
├── pyproject.toml            # مدیریت وابستگی‌ها و تنظیمات ابزارها
├── scripts/                  # اسکریپت‌های عملیاتی (index, quantize, sync_test)
├── src/                      # سورس‌کد اصلی (ماژولار)
│   ├── api/                  # لایهٔ وب: FastAPI، Schemas، Dependencies، Routers، Middleware
│   ├── config/               # تنظیمات، لاگینگ، دانش دامنه (YAML)
│   │   ├── domains/
│   │   │   ├── base.yaml     # پرامپت‌ها (system_extract/extract)، Fast-Path، نگاشت‌های کیفی
│   │   │   └── mobile.yaml   # Slots، Brands، Relaxation، Use-Cases
│   │   ├── domain_loader.py
│   │   ├── logging_config.py
│   │   └── settings.py
│   ├── core/                 # هستهٔ هوش مصنوعی
│   │   ├── llm/              # لایهٔ استخراج نیت/فیلتر و تولید پاسخ (جایگزین کامل NLU)
│   │   │   ├── orchestrator.py   # extract() + generate() + Fallback + Domain Schema Cache
│   │   │   ├── schemas.py        # LLMExtractSchema, LLMResponseSchema, IntentType, MetadataFilters
│   │   │   ├── clients.py        # GroqClient, GeminiClient (async + retry)
│   │   │   ├── memory.py         # ConversationMemory (history + applied_filters)
│   │   │   └── prompt_engine.py  # رندر پویای پرامپت‌ها
│   │   ├── resilience/       # api_resilience.py (Retry + Backoff)
│   │   └── vector/           # Qdrant Indexer، Payload، Retriever
│   │       ├── qdrant_indexer.py
│   │       ├── qdrant_payload.py
│   │       └── qdrant_retriever.py
│   ├── data/                 # لایهٔ داده
│   │   ├── db/               # engine.py, models.py
│   │   ├── fetchers/         # digikala_api.py
│   │   ├── models/           # product.py, api_responses.py
│   │   ├── processing/       # product_pipeline.py
│   │   ├── repositories/     # product_repository.py
│   │   ├── sync/             # digikala_sync.py, progress_tracker.py
│   │   └── transformers/     # product_transformer.py
│   ├── services/             # سرویس‌های مستقل: search, embedding, reranker, sparse_vectorizer, enrichment, query_log,semantic_cache.py
│   └── utils/                # ابزارهای کمکی
│       ├── normalizer.py     # نرمال‌سازی پیشرفتهٔ متن فارسی
│       ├── spec_normalizer.py
│       ├── import_tracker.py
│       └── stracture_project.py
├── test/                     # تست‌های یکپارچه و کیفیت
│   ├── retrival/             # تست‌های بردارسازی، جستجوی ترکیبی، پایپلاین کامل
│   └── test_intent_detection.py
└── uv.lock                   # قفل نسخهٔ پکیج‌ها
```

---

## ⚙️ تصمیمات طراحی کلیدی (Key Design Decisions)

|                     تصمیم                      |                                                                     دلیل فنی (Rationale)                                                                      |                                                            اثر/مزیت (Impact)                                                            |
| :--------------------------------------------: | :-----------------------------------------------------------------------------------------------------------------------------------------------------------: | :-------------------------------------------------------------------------------------------------------------------------------------: |
|              **حذف RAG/Chunking**              |                                                            هر محصول = ۱ سند ساختاریافته در Qdrant                                                             |                                     ✅ حفظ یکپارچگی متادیتا، دقت بالاتر در فیلترگذاری، سادگی ایندکس                                      |
|     **Validation سخت‌گیرانه با Pydantic**      |                                           استفاده از `TypeAdapter(LLMExtractSchema)` + Fail-Fast در صورت خروجی ناقص                                           |                                  ✅ جلوگیری از کرش پایپلاین + لاگ دقیق خطا + حذف کامل `Any` از تایپ‌ها                                   |
|       **استخراج نیت/فیلتر مبتنی بر LLM**       |                                              کاهش بدهی فنی Rule-Based + پوشش بهتر محاوره + مدیریت خودکار Refine                                               |                       افزایش Latency پایه (~۸۰۰ms) + نیاز به Validation سخت‌گیرانه + کاهش >۸۰٪ پیچیدگی کد پارسینگ                       |
|       **پیاده‌سازی Hybrid Search + RRF**       |    ترکیب `Dense` (درک معنایی) + `Sparse` (تطبیق دقیق کلمات کلیدی) + `RRF` (ادغام رتبه‌ها) بهترین Coverage را برای کوئری‌های محاوره‌ای فارسی فراهم می‌کند.     |                                     ✅ پوشش همزمان نیازهای معنایی و کلیدواژه‌ای، کاهش False Negative                                     |
| **عدم استفاده از LangChain/LlamaIndex در MVP** |                                                 کنترل مستقیم بر لایه‌ها، سربار کمتر، دیباگ آسان‌تر، اصل KISS.                                                 |                                             ✅ شفافیت کامل، وابستگی کمتر، سرعت توسعه بالاتر                                              |
|    **بهینه‌سازی ONNX + INT8 Quantization**     |                                                       کاهش مصرف RAM/CPU برای مدل‌های Embedding/Reranker                                                       |                                             ✅ کاهش ~۶۰٪ منابع + حفظ دقت در حد نویز محاسباتی                                             |
|      **تزریق وابستگی و مدیریت چرخه حیات**      |                                    جایگزینی کامل الگوی `Singleton` با `FastAPI Lifespan + app.state Dependency Injection`                                     |     ✅ جداسازی کامل نمونه‌سازی از لاجیک تجاری، حذف `State Leakage` در محیط‌های چند-ورکر، امکان `Mock` کردن سرویس‌ها در تست‌های واحد      |
|       **افزودن `X-API-Key` Middleware**        |                                                      جلوگیری از سوءاستفاده از توکن/سرور در مدل B2B/SaaS                                                       |                                     ✅ کنترل دسترسی، ردیابی مصرف هر فروشگاه، آماده‌سازی برای Billing                                     |
|      **نرمال‌سازی مقادیر فنی به `float`**      |                        تغییر تایپ `ram_gb`, `storage_gb`, `camera_mp` از `int` به `float` و تبدیل خودکار `MB→GB` در لایهٔ Enrichment.                         | ✅ رفع باگ فیلتر کاذب (`32MB == 32GB`)، پذیرش مقادیر اعشاری واقعی (`94.5g`, `0.3MP`) بدون `ValidationError`، دقت بالاتر در کوئری‌های رنج |
|   **ادغام Refine توسط LLM (Context-Aware)**    |                                              سپردن منطق Merge به مدل زبانی با تزریق `$history` و `$last_filters`                                              |                             حذف لاجیک پایتونی `merge_refine_filters` + درک طبیعی تغییرات نسبی («ارزان‌تر»)                              |
|    **معماری Domain-Agnostic Prompt Engine**    | انتقال تمام قالب‌های `system_base` و `templates` به سکشن `prompts:` در YAML. استفاده از `PromptEngine` برای رندر امن متغیرها و تزریق `ConfigDict` در Runtime. |                              ✅ افزودن دامنه جدید یا تغییر لحن/دستورالعمل‌ها فقط نیاز به ویرایش YAML دارد.                               |
|       **فرانت‌اند Vanilla + ES Modules**       |                            حذف سربار `npm/Vite/React` برای فاز دمو با حفظ ساختار تمیز و قابل نگهداری از طریق تفکیک `css/` و `js/`.                            |                     ✅ استقرار تک‌خطی، پایداری بالا، شخصی‌سازی آنی با CSS Variables، تست‌پذیری بهتر لایه‌های کلاینت.                     |
| **دو مرحله‌ای کردن LLM (Extract + Generate)**  |                                                 جداسازی مسئولیت‌ها + امکان کش‌کردن مرحلهٔ اول + دیباگ آسان‌تر                                                 |                           امکان پیاده‌سازی Semantic Cache در فاز بعد + جلوگیری از تداخل Context در پاسخ نهایی                           |
|        **تزریق پویای `$domain_schema`**        |                                         جلوگیری از Hallucination کلید/واحد/مقدار توسط LLM بدون هاردکد کردن در Prompt                                          |                              افزایش دقت استخراج >۹۰٪ + سربار ناچیز توکن (~۱۵۰ توکن) + تطابق ۱۰۰٪ با اسکیما                              |

---

## 🔌 اصول طراحی Prompt برای چند-دامنه‌ای (Domain-Agnostic Prompts)

برای امکان سوئیچ سریع بین دسته‌بندی‌های مختلف (موبایل → هدفون → لپ‌تاپ) بدون تغییر کد:

- ✅ **جداسازی قالب‌ها**: تمام `system_base` و `templates` (search, compare, refine) در سکشن `prompts:` فایل‌های YAML تعریف می‌شوند.
- ✅ **رندر پارامتریک امن**: `PromptEngine` با `string.Template` متغیرهای `$filters` و `$products` را جایگزین می‌کند و از `KeyError` جلوگیری می‌کند.
- ✅ **تزریق پیکربندی در Runtime**: مقادیر توسط `DomainConfigLoader` بارگذاری و Deep Merge شده، به صورت `ConfigDict` به `PromptEngine` و `LLMOrchestrator` تزریق می‌گردند.
- ✅ **Fallback هوشمند**: اگر تمپلیت Intent خاصی در دامنه تعریف نشده باشد، از قالب عمومی `base.yaml` استفاده می‌شود.

```text
System: "تو یک دستیار خرید هوشمند، دقیق و همدل هستی. تنها از اطلاعات محصولات ارائه‌شده استفاده کن..."
User: "کاربر به دنبال محصولی با این ویژگی‌هاست: $filters\nمحصولات بازیابی‌شده:\n$products"
```

---
## 🏗️ معماری استقرار (Deployment Architecture)

> برای جزئیات کامل مدل همکاری و استراتژی بیزینسی، به [PRODUCT.md](PRODUCT.md#🤝-مدل-همکاری-و-تجاری‌سازی-partnership-model) مراجعه کنید.

### 📍 فاز MVP: ایزوله‌سازی فیزیکی
- هر فروشگاه → VPS اختصاصی (Qdrant + PostgreSQL + Redis + ONNX Models)
- **تأثیر فنی**: عدم نیاز به Multi-Tenancy Logic در کد، اما افزایش هزینه زیرساخت

### ⚡ تأثیر بر جریان درخواست (Request Flow)
- **Lazy Loading قیمت**: در مرحله `Post-Retrieval Enrichment`، به جای واکشی از PostgreSQL، باید API فروشگاه فراخوانی شود
- **Cache Layer**: Redis با TTL پویا (1-2 دقیقه برای موبایل، 15-30 دقیقه برای لوازم خانگی)
- **Rate Limiting**: در `ApiKeyMiddleware`، شمارنده Redis بر اساس `client_session_id` یا `IP`

### 🔮 چشم‌انداز فنی (Post-MVP)
- **Remote Model Service**: استخراج ONNX Models از VPSها → سرور مرکزی (کاهش 60% RAM)
- **Multi-Tenant**: مهاجرت به Collection-based Isolation در Qdrant

---
## 🔮 الگوهای معماری برای مقیاس‌پذیری (Post-MVP Patterns)

این بخش الگوهای پیشنهادی برای فیچرهای آینده را بدون تعهد به زمان‌بندی مشخص می‌کند:

### 🧠 لایهٔ هوش و شخصی‌سازی

|فیچر|الگوی پیاده‌سازی پیشنهادی|وابستگی‌ها|ریسک تغییر تکنولوژی|
|:-:|:-:|:-:|:-:|
|**پرفروش‌ترین/تخفیف‌دار/شمارش معکوس**|Tool Calling + Cache لایه‌ای (Redis)|Sync لحظه‌ای قیمت از فروشگاه|🔵 کم (ابزار استاندارد FastAPI)|
|**Personalization + تاریخچه سلیقه**|User Profile Service + Vector Memory per User|Auth + PostgreSQL + Qdrant Collection جداگانه|🟡 متوسط (اگر کاربر >100K، نیاز به بهینه‌سازی برداری)|
|**بازخورد Like/Dislike + یادگیری سبک**|Event-Driven Pipeline + Lightweight Ranking Model|Analytics DB + Feedback Aggregator|🔵 کم (الگوی استاندارد RLHF-lite)|

### 🛒 لایهٔ یکپارچه‌سازی فروشگاه

|فیچر|الگوی پیاده‌سازی پیشنهادی|وابستگی‌ها|ریسک تغییر|
|:-:|:-:|:-:|:-:|
|**اتصال سبد خرید / پروفایل**|OAuth 2.0 + Store API Adapter Pattern|فروشگاه باید API مستند ارائه دهد|🔴 بالا (اگر API ندهد، نیاز به WebView Fallback)|
|**شرایط اقساط + توضیحات مهم**|Knowledge Base + Rule Engine سبک|به‌روزرسانی دستی/نیمه‌خودکار قوانین|🔵 کم|

### 📊 لایهٔ تحلیل و گزارش‌دهی

|فیچر|الگوی پیاده‌سازی پیشنهادی|وابستگی‌ها|ریسک تغییر|
|:-:|:-:|:-:|:-:|
|**لاگ خودکار Intent/Slot + کوئری‌های بدون نتیجه**|Structured Logging → Analytics DB (ClickHouse/Timescale)|Pipeline جمع‌آوری لاگ + Dashboard ساده|🔵 کم|
|**گزارش هفتگی «نیازهای پرجستجو» / «شکاف موجودی»**|Scheduled Job + Template Engine → Email/Dashboard|دسترسی به داده‌های تجمیع‌شده|🔵 کم|

---

## ⚠️ Watchlist: نقاط با ریسک تغییر تکنولوژی

|نقطه|وضعیت فعلی|ریسک آینده|راه‌حل پیشنهادی|
|:-:|:-:|:-:|:-:|
|**شخصی‌سازی در مقیاس بزرگ**|❌ پیاده‌نشده|🟡 اگر کاربران فعال >100,000 شوند، Vector Memory per User سنگین می‌شود|جداسازی Collection کاربران در Qdrant + Sharding هوشمند|
|**Knowledge Graph + استدلال چندمرحله‌ای**|❌ فعلاً با Rule Engine پوشش داده می‌شود|🟡 اگر نیاز به استنتاج پیچیده‌تر پیدا شود، قواعد دستی کافی نیستند|ارزیابی Neo4j + Graph RAG فقط در صورت نیاز واقعی|

---

## 📊 ارزیابی، پایش و بازخورد (Evaluation & Monitoring)

### معیارهای سنجش دوره‌ای

- 🎯 **Faithfulness**: عدم تناقض پاسخ LLM با متادیتای واقعی محصول
- 🔍 **Context Precision**: کیفیت و ارتباط داده‌های بازیابی‌شده با کوئری کاربر
- 💬 **Answer Relevancy**: پاسخ‌دهی دقیق به نیاز واقعی (نه فقط تطبیق کلیدواژه)

### حلقه بازخورد و آنالیتیکس

- 📊 **Light Analytics**: ثبت `query → intent → applied_filters → zero_results_count` برای بهینه‌سازی قواعد و آستانه‌های YAML دامنه
- 🛠️ **Feedback Loop**: گزارش خودکار کوئری‌های `0 نتیجه` برای اضافه کردن Cue/Unit جدید یا تنظیم `relaxation_order`
- 📦 **Dashboard (آینده)**: نمایش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «نرخ تبدیل پیشنهاد»

### ابزارهای پیشنهادی برای ارزیابی

- 🔹 **RAGAS** یا **DeepEval** برای سنجش خودکار کیفیت پاسخ‌ها
- 🔹 **Logging ساختاریافته** با `src/config/logging_config.py` برای ردیابی خطاها
- 🔹 **Semantic Cache Hit-Rate** برای اندازه‌گیری کارایی کش کوئری‌های تکراری
- 🔹 **validate_quantization_drift.py** برای پایش دوره‌ای افت دقت مدل‌های ONNX

---
**نسخه:** 2.4.0 | **آخرین به‌روزرسانی:** 2026/06/26