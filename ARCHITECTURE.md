# 🏗️ معماری فنی

## 🔄 جریان درخواست (Request Flow)

```text
User Input (Farsi)
      │
      ▼
🧩 NLU Pipeline (Hybrid: Rule/Config + Semantic)
  ├─ PersianNormalizer + PersianNumberConverter
  ├─ Intent Detector:
  │     1️⃣ Rule-Based (Fast-Path) →
  │     2️⃣ Semantic Fallback (Embedding E5)
  ├─ TokenParser (Window-Based Matching, Config-Driven via YAML)
  ├─ Slot Filler (Price, Brand, RAM, Storage) + Brand Normalization
  └─ ConflictResolver (حذف خودکار فیلترهای متناقض + اولویت‌بندی فیلتر + تولید warnings)
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
🛍️ Post-Retrieval Enrichment (PostgreSQL)
  └─ واکشی غیرمسدودکنندهٔ image_url و جزئیات تکمیلی برای Top-K نهایی
      │
      ▼
💬 LLM Orchestrator + Context-Aware Memory
  ├─ ConversationMemory (Sliding Window + Filter Merging)
  ├─ Intent: refine → تزریق تاریخچه و ادغام هوشمند فیلترها
  ├─ Groq (Primary) → Gemini (Fallback) → JSON Mode
  └─ Pydantic Validation + Deterministic Fallback
      │
      ▼
✅ Standardized JSON Response → Client

├─ 📦 B2B Contract: `POST /api/v1/search` → JSON (پایدار، کش‌پذیر)
└─ 🌊 UX Stream: `GET /api/v1/search/stream` → SSE (بازخورد لحظه‌ای وضعیت)

   └─ هسته مشترک: `SearchService` (Protocol-Agnostic، اجرای یکپارچه NLU→Retrieval→Rerank→LLM)
```

---

## 🧩 مؤلفه‌های اصلی

|          لایه           |                      مسئولیت                       |                                       پیاده‌سازی فعلی                                       |
| :---------------------: | :------------------------------------------------: | :-----------------------------------------------------------------------------------------: |
|    **Backend Core**     | اجرای یکپارچه پایپلاین بدون وابستگی به پروتکل HTTP |                    `SearchService` (AsyncIterator مشترک برای POST و SSE)                    |
|    **NLU Pipeline**     | نرمال‌سازی، تشخیص نیت، استخراج اسلات، مدیریت تضاد  | `NLUPipeline` + `DomainConfigLoader` (YAML Deep Merge) + `TokenParser` + `ConflictResolver` |
|      **Retrieval**      |    جستجوی ترکیبی و فیلتربرداری هوشمند در Qdrant    |               `QdrantHybridRetriever` (Dense + Sparse + RRF + Smart Fallback)               |
|      **Reranker**       |                مرتب‌سازی نهایی دقیق                |                `RerankerService` (Cross-Encoder، Batch Inference، ONNX INT8)                |
|  **LLM Orchestrator**   |    تولید پاسخ ساختاریافته و مدیریت Prompt پویا     | `LLMOrchestrator` + `PromptEngine` (YAML-Driven، Groq→Gemini Fallback، Pydantic Validation) |
|     **Enrichment**      |    واکشی پویا تصاویر و متادیتا پس از رتبه‌بندی     |                   ProductRepository (Async PostgreSQL + JSONB Extraction)                   |
|       **Memory**        |  مدیریت Context و ادغام فیلترها (Filter Merging)   |                 ConversationMemory (Thread-Safe + Applied Filters Storage)                  |
| **Logging & Telemetry** |       ثبت غیرمسدودکننده کوئری‌ها و وضعیت‌ها        |          `query_log_service.py` (Global Engine + Per-Task AsyncSession، Fail-Safe)          |
|      **Frontend**       |              رابط کاربری دمو و تعامل               |                   Vanilla ES Modules + SSE + Context-Aware Quick Actions                    |

---

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
├── alembic.ini               # تنظیمات اتصال و پیکربندی Alembic
├── data/                     # لاگ‌ها و دیتای تست
│   └── logs/
├── frontend/                 # رابط کاربری دمو
│   ├── index.html            # ساختار معنایی، لینک به استایل‌ها و اسکریپت‌ها
│   ├── css/
│   │   ├── 01-base.css       # توکن‌های طراحی، ریست و تم
│   │   ├── 02-layout.css     # چیدمان صفحه و حالت‌های Welcome/Chat
│		│		 ├── 03-components.css # استایل حباب‌ها، کارت‌ها و دکمه‌های اکشن
│   │   └──  styles.css
│   └── js/
│       ├── script.js         # نقطه ورود (Orchestration) و مدیریت رویدادها
│       ├── session.js        # مدیریت session_id و localStorage
│       ├── api.js            # لایه ارتباط SSE و مدیریت Callbackها
│       └── ui.js             # رندر DOM، پیام‌ها، کارت‌ها و وضعیت
├── models/                   # مدل‌های هوشمند (FP32 & ONNX INT8)
│   └── onnx/
├── pyproject.toml            # مدیریت وابستگی‌ها و تنظیمات ابزارها
├── scripts/                  # اسکریپت‌های تست و سناریوهای یکپارچه
├── src/                      # سورس‌کد اصلی (ماژولار)
│   ├── api/                  # لایهٔ وب: FastAPI، Schemas، Dependencies، Routers، Middleware
│   ├── config/               # تنظیمات، لاگینگ، دانش دامنه (YAML)
│   │   ├── domains/
│   │   │   ├── base.yaml     # قواعد عمومی، نگاشت‌ها، کلمات کلیدی
│   │   │   └── mobile.yaml   # Override دامنه، Cue/Unit اسلات‌ها، Relaxation
│   │   ├── domain_loader.py  # لودر Stateless، Deep Merge، Flatten
│   │   ├── logging_config.py
│   │   └── settings.py
│   ├── core/                 # هستهٔ هوش مصنوعی
│   │   ├── llm/              # Orchestrator، Clients، Memory، Prompts
│   │   ├── nlu/              # Pipeline، Normalizer، Schemas
│   │   │   ├── conflict_resolver.py
│   │   │   ├── model_masker.py
│   │   │   ├── nlu_pipeline.py
│   │   │   ├── normalizer.py
│   │   │   ├── number_converter.py
│   │   │   ├── schemas.py
│   │   │   └── token_parser.py      # جایگزین slot_extractor.py
│   │   └── vector/           # Qdrant Indexer، Payload، Retriever
│   │       ├── qdrant_indexer.py
│   │       ├── qdrant_payload.py
│   │       └── qdrant_retriever.py
│   ├── data/                 # لایهٔ داده: Fetchers، Models، Repositories، Transformers
│   ├── services/             # سرویس‌های مستقل: Embedding، Reranker، Enrichment
│   └── utils/                # ابزارهای کمکی و نرمال‌سازی
├── test/                     # تست‌های یکپارچه و کیفیت
└── uv.lock                   # قفل نسخهٔ پکیج‌ها
```

---

## ⚙️ تصمیمات طراحی کلیدی (Key Design Decisions)

|                     تصمیم                      |                                                                                  دلیل فنی (Rationale)                                                                                  |                                                                     اثر/مزیت (Impact)                                                                      |
| :--------------------------------------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :--------------------------------------------------------------------------------------------------------------------------------------------------------: |
|              **حذف RAG/Chunking**              |                                       هر محصول = ۱ سند ساختاریافته در Qdrant. Chunking باعث تکه‌تکه شدن متادیتا و کاهش دقت فیلترهای عددی می‌شود.                                       |                                               ✅ حفظ یکپارچگی متادیتا، دقت بالاتر در فیلترگذاری، سادگی ایندکس                                               |
|    **معماری Config-Driven Token-Based NLU**    |            حذف Regex شکننده و جایگزینی با `TokenParser` (پنجرهٔ لغزان + Cue/Unit/Operator). تمام قواعد دامنه در `YAML` تعریف شده و توسط `DomainConfigLoader` تزریق می‌شوند.            |    ✅ کاهش ۹۰٪ خطای پارس، پشتیبانی قطعی از رنج عددی (`بین X تا Y`)، نگارش‌های کیفی چندکلمه‌ای، حذف کامل `State Leakage`. هزینهٔ توکن صفر، پایداری ۱۰۰٪.     |
|          **پیاده‌سازی Hybrid Search**          |                 ترکیب `Dense` (درک معنایی) + `Sparse` (تطبیق دقیق کلمات کلیدی) + `RRF` (ادغام رتبه‌ها) بهترین Coverage را برای کوئری‌های محاوره‌ای فارسی فراهم می‌کند.                 |                                              ✅ پوشش همزمان نیازهای معنایی و کلیدواژه‌ای، کاهش False Negative                                               |
|              **اجبار خروجی JSON**              |                     استفاده از `response_format={"type": "json_object"}` + اعتبارسنجی با `pydantic.TypeAdapter`. در صورت شکست، `Deterministic Template` برمی‌گردد.                     |                                       ✅ تضمین ساختار پاسخ برای کلاینت، جلوگیری از خطای پارسینگ، تجربهٔ کاربری پایدار                                       |
| **عدم استفاده از LangChain/LlamaIndex در MVP** |                                                             کنترل مستقیم بر لایه‌ها، سربار کمتر، دیباگ آسان‌تر، اصل KISS.                                                              |                                                       ✅ شفافیت کامل، وابستگی کمتر، سرعت توسعه بالاتر                                                       |
|    **بهینه‌سازی ONNX + INT8 Quantization**     |                    تبدیل مدل‌های `E5` و `bge-reranker` به ONNX Runtime با کوانتایزیشن Dynamic INT8. تأیید شده با Drift Test (`Cosine: 0.0014`, `Spearman: 1.0000`)                     |                                       ✅ کاهش ~۶۰٪ مصرف RAM/CPU، کاهش زمان پاسخ به `<3s`، حفظ دقت در حد نویز محاسباتی                                       |
|      **تزریق وابستگی و مدیریت چرخه حیات**      |                                                 جایگزینی کامل الگوی `Singleton` با `FastAPI Lifespan + app.state Dependency Injection`                                                 |               ✅ جداسازی کامل نمونه‌سازی از لاجیک تجاری، حذف `State Leakage` در محیط‌های چند-ورکر، امکان `Mock` کردن سرویس‌ها در تست‌های واحد               |
|       **افزودن `X-API-Key` Middleware**        |                                                                   جلوگیری از سوءاستفاده از توکن/سرور در مدل B2B/SaaS                                                                   |                                              ✅ کنترل دسترسی، ردیابی مصرف هر فروشگاه، آماده‌سازی برای Billing                                               |
|         **Smart Fallback کانفیگ‌محور**         |                            ترتیب حذف فیلترها، نگاشت شل‌سازی مقادیر (`excellent→good`) و کلمات تأکیدی کاربر (`حتماً، فقط`) مستقیماً از YAML خوانده می‌شوند.                             |             ✅ رتریور ۱۰۰٪ Domain-Agnostic می‌شود. افزودن دامنهٔ جدید بدون تغییر یک خط کد پایتون ممکن است. حفظ تجربهٔ کاربری در شرایط ۰ نتیجه.              |
|      **نرمال‌سازی مقادیر فنی به `float`**      |                                     تغییر تایپ `ram_gb`, `storage_gb`, `camera_mp` از `int` به `float` و تبدیل خودکار `MB→GB` در لایهٔ Enrichment.                                     |          ✅ رفع باگ فیلتر کاذب (`32MB == 32GB`)، پذیرش مقادیر اعشاری واقعی (`94.5g`, `0.3MP`) بدون `ValidationError`، دقت بالاتر در کوئری‌های رنج           |
|   **Dynamic Filter Protection در Fallback**    | ترتیب ثابت حذف فیلترها نیازهای لحظه‌ای کاربر (مثل `حتماً اندروید`) را نادیده می‌گرفت. اسکن کوئری برای کلمات تأکیدی و انتقال فیلتر مرتبط به انتهای صف حذف، تجربهٔ کاربری را حفظ می‌کند. |              ✅ نیاز به تعریف دقیق `filter_cues` در کانفیگ. در صورت عدم تطبیق، رفتار به حالت استاتیک پیش‌فرض برمی‌گردد (Backward Compatible).               |
|    **معماری Domain-Agnostic Prompt Engine**    |             انتقال تمام قالب‌های `system_base` و `templates` به سکشن `prompts:` در YAML. استفاده از `PromptEngine` برای رندر امن متغیرها و تزریق `ConfigDict` در Runtime.              | ✅ افزودن دامنه جدید یا تغییر لحن/دستورالعمل‌ها فقط نیاز به ویرایش YAML دارد. حذف کامل `prompts.py` و هاردکدهای متنی. سازگاری کامل با `refine` و `compare`. |
|           **استراتژی Dual-Endpoint**           |                                   تفکیک نیازهای فروشگاه‌ها (پایداری، کش، JSON استاندارد) از نیازهای UX دمو (کاهش تاخیر ادراکی، نمایش وضعیت لحظه‌ای).                                   |                             ✅ قرارداد B2B کاملاً پایدار و مستقل از پروتکل SSE. کد تکراری با `SearchService` مشترک حذف می‌گردد.                             |
|       **Async Logging با Engine گلوبال**       |                                       جلوگیری از خطای `SessionClosed` در `asyncio.create_task` و حذف سربار ساخت Connection Pool برای هر درخواست.                                       |                                ✅ لاگ‌گیری کاملاً Non-Blocking و ایمن. Latency کل چرخه تحت تأثیر نوشتن در DB قرار نمی‌گیرد.                                 |
|       **فرانت‌اند Vanilla + ES Modules**       |                                        حذف سربار `npm/Vite/React` برای فاز دمو با حفظ ساختار تمیز و قابل نگهداری از طریق تفکیک `css/` و `js/`.                                         |                              ✅ استقرار تک‌خطی، پایداری بالا، شخصی‌سازی آنی با CSS Variables، تست‌پذیری بهتر لایه‌های کلاینت.                               |
|             **معماری Hybrid NLU**              |                                                     ترکیب Rule-Based (سرعت) و Semantic Embedding (دقت) برای پوشش جملات محاوره‌ای.                                                      |                                                ✅ تشخیص نیت دقیق بدون سربار LLM + دقت >95% در تست‌های چالشی                                                 |
|            **Brand Normalization**             |                                                        مپ کردن مترادف‌ها و تایپوها (مثل آیفون/ایفون ← اپل) در لایه TokenParser.                                                        |                                                ✅ جلوگیری از خطای جستجو و افزایش رضایت کاربر با زبان غیررسمی                                                |

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

- 🎯 **`Faithfulness`**: عدم تناقض پاسخ LLM با متادیتای واقعی محصول
- 🔍 **`Context Precision`**: کیفیت و ارتباط داده‌های بازیابی‌شده با کوئری کاربر
- 💬 **`Answer Relevancy`**: پاسخ‌دهی دقیق به نیاز واقعی (نه فقط تطبیق کلیدواژه)
- ⏱️ **`Latency`**: `<3s` برای کل چرخه (NLU → Retrieval → Rerank → LLM)

### حلقه بازخورد و آنالیتیکس

- 📊 **Light Analytics**: ثبت `query → intent → applied_filters → zero_results_count` برای بهینه‌سازی قواعد و آستانه‌های YAML دامنه
- 🛠️ **Feedback Loop**: گزارش خودکار کوئری‌های `0 نتیجه` برای اضافه کردن Cue/Unit جدید یا تنظیم `relaxation_order`
- 📦 **Dashboard (آینده)**: نمایش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «نرخ تبدیل پیشنهاد»

### ابزارهای پیشنهادی برای ارزیابی

- 🔹 **RAGAS** یا **DeepEval** برای سنجش خودکار کیفیت پاسخ‌ها
- 🔹 **Logging ساختاریافته** با `src/config/logging_config.py` برای ردیابی خطاها
- 🔹 **Semantic Cache Hit-Rate** برای اندازه‌گیری کارایی کش کوئری‌های تکراری
- 🔹 **`validate_quantization_drift.py`** برای پایش دوره‌ای افت دقت مدل‌های ONNX

---
**نسخه:** 1.0.0 | **آخرین به‌روزرسانی:** 2026/05/05