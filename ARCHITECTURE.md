# 🏗️ معماری فنی

## 🔄 جریان درخواست (Request Flow)

```text
User Input (Farsi)
      │
      ▼
🧩 NLU Pipeline (Rule-Based)
  ├─ PersianNormalizer (Fast translate + ZWNJ fix)
  ├─ Intent Detector (Regex + Domain Knowledge)
  └─ Slot Filler (Price, Brand, RAM, Qualitative → Filters)
      │
      ▼
🔍 Hybrid Retrieval (Qdrant)
  ├─ Dense Vector (E5 Embedding)
  ├─ Sparse Vector (BM25 Hash)
  ├─ Metadata Filters (price, brand, tags, etc.)
  └─ Fusion: RRF (Reciprocal Rank Fusion)
      │
      ▼
⚖️ Reranker Service
  └─ Cross-Encoder (bge-reranker-v2-m3) → Top 3
      │
      ▼
💬 LLM Orchestrator + Memory
  ├─ Groq (Primary) → JSON Mode
  ├─ Gemini (Fallback) → JSON Mode
  ├─ Pydantic Validation (Strict Schema)
  └─ Deterministic Fallback (If both fail)
      │
      ▼
✅ Structured JSON Response → Client
```

---

## 🧩 مؤلفه‌های اصلی

|         لایه         |               مسئولیت                |                                     پیاده‌سازی فعلی                                     |
| :------------------: | :----------------------------------: | :-------------------------------------------------------------------------------------: |
|   **NLU Pipeline**   | نرمال‌سازی، تشخیص نیت، استخراج فیلتر |     `NLUPipeline` + `domain_knowledge.json` (Rule-Based، سرعت آنی، هزینه توکن صفر)      |
|    **Retrieval**     |       جستجوی ترکیبی در Qdrant        |        `QdrantHybridRetriever` (Dense E5 + Sparse BM25 + RRF + Metadata Filter)         |
|     **Reranker**     |         مرتب‌سازی نهایی دقیق         |         `RerankerService` (`bge-reranker-v2-m3` Cross-Encoder، Batch Inference)         |
| **LLM Orchestrator** |        تولید پاسخ ساختاریافته        | `LLMOrchestrator` (Groq→Gemini Fallback + `response_format=json` + Pydantic Validation) |
|      **Memory**      |        مدیریت Context مکالمه         |     `ConversationMemory` (Sliding Window `max=3`، Session-based UUID، Thread-Safe)      |


## 📂 ساختار پروژه (Project Structure)

```text
├── .env
├── .gitignore
├── .style.yapf
├── alembic/                  # مدیریت مایگریشن‌های دیتابیس
│   ├── versions/
│   └── ...
├── data/                     # لاگ‌ها و دیتای تست
│   ├── logs/
│   └── test/
├── pyproject.toml            # مدیریت وابستگی‌ها و تنظیمات ابزارها
├── scripts/                  # اسکریپت‌های تست و سناریوهای یکپارچه
├── src/                      # سورس‌کد اصلی (ماژولار)
│   ├── api/                  # لایهٔ وب: FastAPI، Schemas، Dependencies
│   ├── config/               # تنظیمات، لاگینگ، دانش دامنه (JSON)
│   ├── core/                 # هستهٔ هوش مصنوعی
│   │   ├── llm/              # Orchestrator، Clients، Memory، Prompts
│   │   ├── nlu/              # Pipeline، Normalizer، Schemas
│   │   ├── resilience/       # مدیریت خطا و Retry APIها
│   │   └── vector/           # Qdrant Indexer، Payload، Retriever
│   ├── data/                 # لایهٔ داده: Fetchers، Models، Repositories، Transformers
│   ├── services/             # سرویس‌های مستقل: Embedding، Reranker، Enrichment
│   └── utils/                # ابزارهای کمکی و نرمال‌سازی
└── uv.lock                   # قفل نسخهٔ پکیج‌ها
---
```

## ⚙️ تصمیمات طراحی کلیدی (Key Design Decisions)

|                     تصمیم                      |                                                                  دلیل فنی (Rationale)                                                                  |                               اثر/مزیت (Impact)                                |
| :--------------------------------------------: | :----------------------------------------------------------------------------------------------------------------------------------------------------: | :----------------------------------------------------------------------------: |
|              **حذف RAG/Chunking**              |                       هر محصول = ۱ سند ساختاریافته در Qdrant. Chunking باعث تکه‌تکه شدن متادیتا و کاهش دقت فیلترهای عددی می‌شود.                       |         ✅ حفظ یکپارچگی متادیتا، دقت بالاتر در فیلترگذاری، سادگی ایندکس         |
|         **استفاده از Rule-Based NLU**          |                 `NLUPipeline` + `domain_knowledge.json` تشخیص نیت را **بدون تأخیر شبکه، بدون هزینه توکن و با دقت قطعی** انجام می‌دهد.                  |      ✅ کاهش Latency، هزینهٔ صفر توکن برای Intent Detection، پایداری ۱۰۰٪       |
|          **پیاده‌سازی Hybrid Search**          | ترکیب `Dense` (درک معنایی) + `Sparse` (تطبیق دقیق کلمات کلیدی) + `RRF` (ادغام رتبه‌ها) بهترین Coverage را برای کوئری‌های محاوره‌ای فارسی فراهم می‌کند. |        ✅ پوشش همزمان نیازهای معنایی و کلیدواژه‌ای، کاهش False Negative         |
|              **اجبار خروجی JSON**              |     استفاده از `response_format={"type": "json_object"}` + اعتبارسنجی با `pydantic.TypeAdapter`. در صورت شکست، `Deterministic Template` برمی‌گردد.     | ✅ تضمین ساختار پاسخ برای کلاینت، جلوگیری از خطای پارسینگ، تجربهٔ کاربری پایدار |
|        **مدیریت Rate Limit پلن رایگان**        |                            `Retry` با `Exponential Backoff` روی خطای `429` + Fallback خودکار به سرویس دوم (Groq → Gemini).                             |     ✅ پایداری سرویس با وجود محدودیت‌های API رایگان، کاهش خطای کاربر نهایی      |
| **عدم استفاده از LangChain/LlamaIndex در MVP** |                                             کنترل مستقیم بر لایه‌ها، سربار کمتر، دیباگ آسان‌تر، اصل KISS.                                              |                 ✅ شفافیت کامل، وابستگی کمتر، سرعت توسعه بالاتر                 |

---

## 📦 لوله داده (Data Pipeline)

```text
1️⃣ Acquisition → DigikalaAPIClient
   ├─ Async + Semaphore=3 + Random Delay
   ├─ Pagination هوشمند (سقف ۱۰۰ صفحه)
   └─ مدیریت خطای 400/429 با Retry

2️⃣ Persistence → PostgreSQL
   ├─ جدول product_raw_cache (JSONB)
   ├─ ON CONFLICT DO UPDATE برای به‌روزرسانی ایمن
   └─ ProgressTracker برای Resume خودکار

3️⃣ Enrichment → ProductEnrichmentService
   ├─ price_range: budget/mid/premium/flagship
   ├─ battery_quality/camera_quality: excellent/good/average/poor
   ├─ value_for_money: good/average/poor
   └─ tags: gaming, photography, lightweight, premium_build, ...

4️⃣ Indexing → QdrantIndexer
   ├─ تک‌سند به‌ازای هر محصول (بدون Chunking)
   ├─ Payload Indexes: INTEGER (price), KEYWORD (brand/tags), BOOL (is_available)
   └─ Collection: nira_products_mvp (Cosine distance, configurable dims)
```

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
|          **ورودی صوتی فارسی**          |  STT Service (Whisper API) → متن → NLU Pipeline   |      API خارجی + مدیریت خطای تبدیل گفتار      | 🟡 متوسط (اگر هزینه API بالا رفت، مهاجرت به مدل محلی کوچک) |

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
|                  **ورودی صوتی**                  |              ❌ پیاده‌نشده               |    🟡 اگر حجم درخواست بالا برود، هزینهٔ Whisper API افزایش می‌یابد     |        مهاجرت به مدل محلی کوچک (Whisper-tiny) یا سرویس ابری جایگزین        |
|           **شخصی‌سازی در مقیاس بزرگ**            |              ❌ پیاده‌نشده               | 🟡 اگر کاربران فعال >100,000 شوند، Vector Memory per User سنگین می‌شود |           جداسازی Collection کاربران در Qdrant + Sharding هوشمند           |
|    **Knowledge Graph + استدلال چندمرحله‌ای**     | ❌ فعلاً با Rule Engine پوشش داده می‌شود |   🟡 اگر نیاز به استنتاج پیچیده‌تر پیدا شود، قواعد دستی کافی نیستند    |              ارزیابی Neo4j + Graph RAG فقط در صورت نیاز واقعی              |
| **ابزارهای اورکستراسیون (LangChain/LlamaIndex)** |          ❌ عمداً استفاده نشده           |     🔵 اگر تعداد Toolها >5 شد و نیاز به Dynamic Routing پیدا کردیم     | مهاجرت تدریجی لایهٔ Orchestrator به LangGraph (بدون بازنویسی سایر لایه‌ها) |

---

## 📊 ارزیابی، پایش و بازخورد (Evaluation & Monitoring)

### معیارهای سنجش دوره‌ای

- 🎯 **`Faithfulness`**: عدم تناقض پاسخ LLM با متادیتای واقعی محصول
- 🔍 **`Context Precision`**: کیفیت و ارتباط داده‌های بازیابی‌شده با کوئری کاربر
- 💬 **`Answer Relevancy`**: پاسخ‌دهی دقیق به نیاز واقعی (نه فقط تطبیق کلیدواژه)
- ⏱️ **`Latency`**: `<1.5s` برای کل چرخه (NLU → Retrieval → Rerank → LLM)

### حلقه بازخورد و آنالیتیکس

- 📊 **Light Analytics**: ثبت `query → intent → applied_filters → zero_results_count` برای بهینه‌سازی `domain_knowledge.json`
- 🛠️ **Feedback Loop**: گزارش خودکار کوئری‌های `0 نتیجه` برای اضافه کردن قواعد جدید یا به‌روزرسانی آستانه‌ها
- 📦 **Dashboard (آینده)**: نمایش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «نرخ تبدیل پیشنهاد»

### ابزارهای پیشنهادی برای ارزیابی

- 🔹 **RAGAS** یا **DeepEval** برای سنجش خودکار کیفیت پاسخ‌ها
- 🔹 **Logging ساختاریافته** با `src/config/logging_config.py` برای ردیابی خطاها
- 🔹 **Semantic Cache Hit-Rate** برای اندازه‌گیری کارایی کش کوئری‌های تکراری