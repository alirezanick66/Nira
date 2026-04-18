# 🗺️ Roadmap

---

## 📊 وضعیت کلی پروژه

|          فاز          |     وضعیت      |                               هدف کلیدی                                |
| :-------------------: | :------------: | :--------------------------------------------------------------------: |
|      **🟢 MVP**       |    ✅ تکمیل     |       اثبات مفهوم: NLU → Retrieval → Rerank → LLM JSON → FastAPI       |
| **🟡 MVP Refinement** | 🟡 In Progress |          رفع نقص‌های فنی MVP + بهبود دقت استخراج و رتبه‌بندی           |
|   **🔵 Post-MVP 1**   |   🔵 Planned   | تجربه کاربری هوشمندتر: Cache، Personalization، Feedback، Clarification |
|   **🔵 Post-MVP 2**   |   🔵 Planned   |       یکپارچه‌سازی فروشگاه: سبد خرید، اقساط، Analytics، Compare        |
|   **🔵 Post-MVP 3**   |   🔵 Planned   |          مقیاس‌پذیری فنی: ONNX، Multi-Domain، Evaluation Loop          |

---

## 🟢 فاز MVP (تکمیل‌شده)

### ✅ اهداف محقق‌شده

- [x] **NLU Pipeline قاعده‌محور**: نرمال‌سازی فارسی + تشخیص نیت + استخراج فیلتر بدون هزینه توکن
- [x] **Hybrid Retrieval**: ترکیب Dense (E5) + Sparse (BM25) + RRF در Qdrant
- [x] **Reranker Service**: مرتب‌سازی نهایی با `bge-reranker-v2-m3`
- [x] **LLM Orchestrator**: Groq (Primary) + Gemini (Fallback) + JSON Validation
- [x] **Conversation Memory**: Sliding Window (`max=3`) + Session-based UUID
- [x] **FastAPI Endpoint**: `/api/v1/search` با Lifespan + Dependency Injection
- [x] **Product Enrichment**: استنتاج قطعی `price_range`, `quality_levels`, `tags`
- [x] **Data Pipeline**: Acquisition → PostgreSQL → Enrichment → Qdrant Indexing

---

## 🟡 فاز MVP Refinement (بهبودهای فنی فوری)

### 🎯 اهداف کلیدی

|                  فیچر                  |                                                               توضیح                                                               |  اولویت  |               وابستگی‌ها                |                       معیار موفقیت                       |
| :------------------------------------: | :-------------------------------------------------------------------------------------------------------------------------------: | :------: | :-------------------------------------: | :------------------------------------------------------: |
|   **🔢 پارسینگ پیشرفته اعداد/واحد**    |              پشتیبانی از «سی میلیون»، «30تومن»، «حدود ۴۰-۵۰» + فیلتر کردن اعداد مدل (`15`, `S24`) بدون Regex شکننده               | 🔴 بالا  | `NLUPipeline` + `domain_knowledge.json` |     کاهش ۹۰٪ خطای استخراج عدد از کوئری‌های محاوره‌ای     |
| **⚖️ تفکیک واحد (GB/MB) در Embedding** | آموزش/تنظیم Payload به‌گونه‌ای که `32GB RAM` با `32MB Storage` اشتباه گرفته نشود (تفکیک در `ProductEnrichment` + `QdrantIndexer`) | 🔴 بالا  |   `product.py` + `qdrant_payload.py`    | عدم بازگشت محصولات با واحد ناسازگار در فیلترهای رم/حافظه |
|     **🎚️ تنظیم آستانه Reranking**     |                  کالیبراسیون `min_score` در `RerankerService` بر اساس دادهٔ واقعی (تعادل بین Precision و Recall)                  | 🔴 بالا  |       لاگ‌های Reranking + تست A/B       |  کاهش نتایج نامرتبط در Top-3 بدون افزایش False Negative  |
|   **🔄 Smart Fallback (0 Results)**    |               حذف خودکار سخت‌ترین فیلتر (مثلاً `weight_g` یا `camera_quality`) و تلاش مجدد در صورت عدم یافتن نتیجه                | 🟡 متوسط |         `QdrantHybridRetriever`         |       کاهش ۵۰٪ کوئری‌های `0 نتیجه` بدون افت کیفیت        |
|       **🧩 مدیریت تضاد فیلترها**       |                    تشخیص کوئری‌های متناقض (`«ارزون ولی پرچم‌دار»`) → هشدار به کاربر یا اعمال اولویت‌بندی پویا                     | 🟡 متوسط |   `NLUPipeline` + `LLM Orchestrator`    | جلوگیری از بازگشت نتایج نامربوط به‌خاطر فیلترهای متناقض  |

### 📦 خروجی‌های مورد انتظار
- [ ] به‌روزرسانی `_extract_slots` در `nlu_pipeline.py` با Regex هوشمند + واحدسنج
- [ ] افزودن فیلد `unit` به `QdrantProductPayload` برای رم/حافظه/باتری
- [ ] اسکریپت `calibrate_reranker.py` برای یافتن `min_score` بهینه
- [ ] لاجیک `relaxed_filters` در `QdrantHybridRetriever.search()`
- [ ] الگوی `ConflictResolver` در `NLUPipeline` با اولویت‌بندی `price > brand > specs`

---

## 🔵 فاز Post-MVP 1: تجربه کاربری هوشمندتر

### 🎯 اهداف کلیدی
|              فیچر              |                                          توضیح                                          |  اولویت  |                     وابستگی‌ها                     |                        معیار موفقیت                         |
| :----------------------------: | :-------------------------------------------------------------------------------------: | :------: | :------------------------------------------------: | :---------------------------------------------------------: |
|     **🧠 Semantic Cache**      |                 کش برداری کوئری‌های تکراری + TTL برای کاهش توکن و تأخیر                 | 🔴 بالا  |             Qdrant + Embedding Service             |          کاهش ۴۰٪ مصرف توکن برای کوئری‌های تکراری           |
|   **💬 Clarification Loop**    | پرسش هدایت‌گر هوشمند وقتی کوئری کاربر مبهم است (`«منظورتون گوشی اندرویده یا آیفونه؟»`)  | 🔴 بالا  |   NLU Confidence Score + LLM Prompt Engineering    |      کاهش ۳۰٪ کوئری‌های `0 نتیجه` + افزایش رضایت کاربر      |
|  **👤 Personalization Lite**   |      ذخیره سلیقه کاربر (برند/رنج قیمت/تگ‌های موردعلاقه) + پیشنهاد مبتنی بر تاریخچه      | 🔴 بالا  |         Auth + PostgreSQL + Vector Memory          |       افزایش ۲۰٪ نرخ کلیک روی پیشنهادات شخصی‌سازی‌شده       |
|     **🔄 Refine + Memory**     | پشتیبانی کامل از `Intent: refine` (`«ارزون‌تر»، «سبک‌تر»`) با استفاده از تاریخچه مکالمه | 🔴 بالا  | `ConversationMemory` + Context Injection در Prompt |        درک صحیح مرجع مقایسه در ۹۵٪ کوئری‌های refine         |
|  **👍 بازخورد Like/Dislike**   |          ثبت بازخورد کاربر روی پیشنهاد + یادگیری سبک سلیقه (بدون Fine-tuning)           | 🟡 متوسط |     Feedback Endpoint + Lightweight Aggregator     | امکان به‌روزرسانی `domain_knowledge.json` بر اساس بازخوردها |
| **🕐 زمان‌آگاهی (Time-Aware)** |      تشخیص زمان ایران برای پیام‌های هوشمند (`عصر بخیر`) + شمارش معکوس پایان تخفیف       | 🟢 پایین |         Timezone Service + Store API Sync          |     نمایش صحیح زمان باقی‌مانده برای ۹۵٪ تخفیف‌های فعال      |

### 📦 خروجی‌های مورد انتظار
- [ ] ماژول `SemanticCacheService` با پشتیبانی از TTL و Invalidation
- [ ] الگوی پرامپت `Clarification Prompt` در `PromptEngine` + لاجیک `confidence_threshold`
- [ ] جدول `user_preferences` در PostgreSQL + Endpoint `/api/v1/profile`
- [ ] به‌روزرسانی `LLMOrchestrator` برای تزریق `last_n_messages` به Context
- [ ] Endpoint `/api/v1/feedback` با Aggregator سبک + به‌روزرسانی خودکار `domain_knowledge.json`
- [ ] سرویس `TimeAwareService` با پشتیبانی از `Asia/Tehran`

---

## 🔵 فاز Post-MVP 2: یکپارچه‌سازی فروشگاه

### 🎯 اهداف کلیدی
|              فیچر               |                                                 توضیح                                                 |  اولویت  |                  وابستگی‌ها                   |                               معیار موفقیت                               |
| :-----------------------------: | :---------------------------------------------------------------------------------------------------: | :------: | :-------------------------------------------: | :----------------------------------------------------------------------: |
|      **🛒 اتصال سبد خرید**      |               افزودن محصول پیشنهادی به سبد خرید فروشگاه با OAuth 2.0 + Adapter Pattern                | 🔴 بالا  |       فروشگاه باید API مستند ارائه دهد        |               امکان افزودن محصول با ۱ کلیک از پاسخ دستیار                |
|  **🔍 Intent: Compare Engine**  | تولید جدول مقایسه‌ای یا متن تحلیلی بین ۲-۳ محصول برتریافته (`بین آیفون 15 و سامسونگ S24 کدوم بهتره؟`) | 🟡 متوسط | `LLM Orchestrator` + Structured Output Schema |              تولید پاسخ مقایسه‌ای ساختاریافته در ۹۰٪ موارد               |
|       **💳 شرایط اقساط**        |                    نمایش خودکار شرایط اقساط + محاسبه قسط ماهانه بر اساس قیمت محصول                    | 🟡 متوسط |       Knowledge Base + Rule Engine سبک        |                   پوشش ۱۰۰٪ محصولات دارای گزینه اقساط                    |
| **📊 Analytics Dashboard Lite** |               گزارش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «محصولات پربازدید بدون خرید»                | 🟡 متوسط |   Structured Logging + ClickHouse/Timescale   |                گزارش هفتگی خودکار برای تیم محصول فروشگاه                 |
|    **🎙️ ورودی صوتی (STT)**     |                        پردازش گفتار فارسی → متن → NLU Pipeline با Whisper API                         | 🟢 پایین |      API خارجی + مدیریت خطای تبدیل گفتار      |                 دقت تبدیل گفتار >۹۰٪ برای کوئری‌های رایج                 |
|   **🔍 تحلیل پیشرفته نظرات**    |         استخراج خودکار مزایا/معایب از نظرات کاربران با LLM سبک + به‌روزرسانی `user_feedback`          | 🟢 پایین |       Review Scraper + Lightweight LLM        | به‌روزرسانی خودکار `battery_quality`/`camera_quality` بر اساس نظرات جدید |

### 📦 خروجی‌های مورد انتظار
- [ ] `StoreAdapter` Interface + پیاده‌سازی Digikala
- [ ] ماژول `ComparePromptEngine` + Schema اعتبارسنجی پاسخ مقایسه‌ای
- [ ] ماژول `InstallmentCalculator` با قواعد قابل‌پیکربندی
- [ ] Dashboard ساده با Grafana یا Streamlit
- [ ] سرویس `STTService` با Fallback به متن دستی
- [ ] Job دوره‌ای `ReviewAnalyzer` با Rate Limit هوشمند

---

## 🔵 فاز Post-MVP 3: مقیاس‌پذیری فنی

### 🎯 اهداف کلیدی
|                 فیچر                 |                                                          توضیح                                                           |  اولویت  |                  وابستگی‌ها                  |                          معیار موفقیت                           |
| :----------------------------------: | :----------------------------------------------------------------------------------------------------------------------: | :------: | :------------------------------------------: | :-------------------------------------------------------------: |
|   **⚡ ONNX Export + Quantization**   |               تبدیل مدل‌های `E5` و `bge-reranker` به ONNX + Quantization (INT8) برای کاهش ۶۰٪ مصرف RAM/CPU               | 🔴 بالا  |       `optimum[onnxruntime]` + تست دقت       |        کاهش Latency Embedding/Rerank به `<100ms` روی CPU        |
| **🌍 Domain-Agnostic Prompt Engine** | سوئیچ آسان بین موبایل/هدفون/لپ‌تاپ با `domain_knowledge.json` + Prompt Parametric (`{domain_topic}`, `{key_attributes}`) | 🟡 متوسط |   Refactor `PromptEngine` + Domain Router    |          افزودن دامنه جدید در `<1 ساعت` بدون تغییر کد           |
|        **📐 Evaluation Loop**        |                          سنجش خودکار کیفیت با `RAGAS`/`DeepEval` + گزارش بنچمارک پس از هر تغییر                          | 🟡 متوسط |       Test Dataset + CI/CD Integration       |             جلوگیری از Regression در کیفیت پاسخ‌ها              |
|  **🕸️ Knowledge Graph (ارزیابی)**   |                        بررسی Neo4j + Graph RAG برای استدلال چندمرحله‌ای (فقط در صورت نیاز واقعی)                         | 🟢 پایین |    Graph Schema Design + Query Benchmark     | اثبات برتری Graph RAG نسبت به Hybrid Search در سناریوهای پیچیده |
|       **🔄 Event-Driven Sync**       |                        آپدیت لحظه‌ای قیمت/موجودی با Webhook + Message Queue (Redis Streams/Kafka)                        | 🟢 پایین | Store Webhook Support + Queue Infrastructure |       تاخیر آپدیت قیمت <۵ دقیقه از لحظه تغییر در فروشگاه        |
|      **🐳 Docker & Deployment**      |                        `docker-compose` برای Qdrant, Postgres, FastAPI + تنظیمات Production-ready                        | 🟡 متوسط |       Dockerfile بهینه + Health Checks       |       استقرار یک‌خطی در محیط جدید با `docker-compose up`        |

### 📦 خروجی‌های مورد انتظار
- [ ] اسکریپت `export_onnx.py` + Benchmark Report (دقت vs سرعت)
- [ ] `DomainRouter` + Template System برای Promptهای پارامتریک
- [ ] GitHub Action برای اجرای خودکار `RAGAS` روی PRها
- [ ] PoC Graph RAG با Neo4j + مقایسه دقت/هزینه
- [ ] سرویس `SyncWorker` با پشتیبانی از Redis Streams
- [ ] `docker-compose.prod.yml` + `.env.example` + Health Check Endpoint

---

## ⚠️ ریسک‌ها و راه‌کارهای کاهش

|                    ریسک                    |  احتمال  |         تأثیر          |                               راه‌کار کاهش                               |
| :----------------------------------------: | :------: | :--------------------: | :----------------------------------------------------------------------: |
|        **وابستگی به API دیجی‌کالا**        | 🟡 متوسط |        🔴 بالا         |        طراحی `StoreAdapter` Interface از هم‌اکنون + Mock برای تست        |
|       **هزینهٔ APIهای LLM در مقیاس**       | 🟡 متوسط |        🟡 متوسط        |              Semantic Cache + ONNX + Fallback به مدل سبک‌تر              |
|    **پیچیدگی شخصی‌سازی در مقیاس بزرگ**     | 🔵 پایین |        🟡 متوسط        |   شروع با `user_preferences` ساده + مهاجرت تدریجی به Vector DB جداگانه   |
| **تغییر سیاست‌های پلن رایگان Groq/Gemini** | 🟡 متوسط |        🟡 متوسط        |     پشتیبانی از چندین Provider + قابلیت سوییچ سریع در `settings.py`      |
|   **نیاز به استدلال چندمرحله‌ای پیچیده**   | 🔵 پایین |        🔴 بالا         | ارزیابی Knowledge Graph فقط پس از جمع‌آوری دادهٔ کافی از کوئری‌های واقعی |
|      **اشتباه گرفتن واحدها (GB/MB)**       | 🟡 متوسط | 🔴 بالا (تجربه کاربری) |     تفکیک صریح `unit` در Payload + اعتبارسنجی در `ProductEnrichment`     |
