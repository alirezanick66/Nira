# 🗺️ Roadmap

📍 **وضعیت فعلی پروژه:** ✅ پایان فاز `MVP Refinement` | آماده‌سازی دمو و استانداردسازی API

## 📊 وضعیت کلی پروژه

|        فاز        |   وضعیت    |                                     هدف کلیدی                                     |
| :---------------: | :--------: | :-------------------------------------------------------------------------------: |
|      🟢 MVP       |  ✅ تکمیل   |            اثبات مفهوم: NLU → Retrieval → Rerank → LLM JSON → FastAPI             |
| 🟢 MVP Refinement |  ✅ تکمیل   |                رفع نقص‌های فنی MVP + بهبود دقت استخراج و رتبه‌بندی                |
|   🔵 Post-MVP 1   | 🔵 Planned | تجربه کاربری هوشمندتر: Cache، Personalization، Feedback، Clarification،Time-Aware |
|   🔵 Post-MVP 2   | 🔵 Planned |             یکپارچه‌سازی فروشگاه: سبد خرید، اقساط، Analytics، Compare             |
|   🔵 Post-MVP 3   | 🔵 Planned |        مقیاس‌پذیری فنی: Multi-Domain، Evaluation Loop، Docker،Token-Parser        |
|                   |            |                                                                                   |

---

## 🟢 فاز MVP (تکمیل‌شده)
### ✅ اهداف محقق‌شده
- [x] **NLU Pipeline قاعده‌محور**: نرمال‌سازی فارسی + تشخیص نیت + استخراج فیلتر بدون هزینه توکن
- [x] **Hybrid Retrieval**: ترکیب Dense (E5) + Sparse (BM25) + RRF در Qdrant
- [x] **Reranker Service**: مرتب‌سازی نهایی با `bge-reranker-v2-m3`
- [x] **LLM Orchestrator**: Groq (Primary) + Gemini (Fallback) + JSON Validation
- [x] **Conversation Memory**: Sliding Window (`max=3`) + Session-based UUID
- [x] FastAPI Endpoint: `/api/v1/search` با Lifespan + Dependency Injection
- [x] **Product Enrichment**: استنتاج قطعی `price_range`, `quality_levels`, `tags`
- [x] **Data Pipeline**: Acquisition → PostgreSQL → Enrichment → Qdrant Indexing
- [x] **Frontend Demo**: Vanilla SPA + Typewriter Effect + Session Memory + Theme Customization
- [x] **ONNX + INT8 Quantization**: کاهش ~۶۰٪ مصرف منابع + تأییدیه Drift (Cosine: `0.0014`)

---

## 🟢 فاز MVP Refinement (بهبودهای فنی فوری)
### 🎯 اهداف کلیدی

|                  فیچر                  |                                                 توضیح                                                  | اولویت  |                وابستگی‌ها                 |                             معیار موفقیت                              |
| :------------------------------------: | :----------------------------------------------------------------------------------------------------: | :-----: | :---------------------------------------: | :-------------------------------------------------------------------: |
|   **🔢 پارسینگ پیشرفته اعداد/واحد**    | پشتیبانی از «سی میلیون»، «30تومن»، «حدود ۴۰-۵۰» + فیلتر کردن اعداد مدل (`15`, `S24`) بدون Regex شکننده | ✅ تکمیل |  NLUPipeline + YAML Config (TokenParser)  |           کاهش ۹۰٪ خطای استخراج عدد از کوئری‌های محاوره‌ای            |
| **⚖️ تفکیک واحد (GB/MB) در Embedding** |            آموزش/تنظیم Payload به‌گونه‌ای که `32GB RAM` با `32MB Storage` اشتباه گرفته نشود            | ✅ تکمیل |    `product.py` + `qdrant_payload.py`     |       عدم بازگشت محصولات با واحد ناسازگار در فیلترهای رم/حافظه        |
|   **🔄 Smart Fallback (0 Results)**    |                     حذف خودکار سخت‌ترین فیلتر و تلاش مجدد در صورت عدم یافتن نتیجه                      | ✅ تکمیل |          `QdrantHybridRetriever`          |              کاهش ۵۰٪ کوئری‌های `0 نتیجه` بدون افت کیفیت              |
|       **🧩 مدیریت تضاد فیلترها**       |               تشخیص کوئری‌های متناقض («ارزون ولی پرچم‌دار») → هشدار یا اولویت‌بندی پویا                | ✅ تکمیل |      NLUPipeline + ConflictResolver       |        جلوگیری از بازگشت نتایج نامربوط به‌خاطر فیلترهای متناقض        |
|       ⚖️ **گارد منطقی رم/حافظه**       |                اعمال فیلتر بازه معتبر (1≤ram≤64) در Payload + نرمال‌سازی در Enrichment                 | ✅ تکمیل | `qdrant_payload.py` + `ProductEnrichment` | حذف نتایج غیرواقعی (مثل ۳۲ مگابایت رم) بدون نیاز به فیلد `unit` اضافی |

### 📦 خروجی‌های مورد انتظار
- [x] به‌روزرسانی `_extract_slots` در `nlu_pipeline.py` با Regex هوشمند + واحدسنج
- [x] افزودن فیلد `unit` به `QdrantProductPayload` برای رم/حافظه/باتری
- [x] لاجیک `relaxed_filters` در `QdrantHybridRetriever.search()`
- [x] الگوی `ConflictResolver` در `NLUPipeline` با اولویت‌بندی `price > brand > specs`

---

## 🔵 فاز Post-MVP 1: تجربه کاربری هوشمندتر
### 🎯 اهداف کلیدی
|               فیچر               |                             توضیح                              |  اولویت  |                وابستگی‌ها                 |                    معیار موفقیت                    |
| :------------------------------: | :------------------------------------------------------------: | :------: | :---------------------------------------: | :------------------------------------------------: |
|  **🕐 زمان‌آگاهی (Time-Aware)**  |   تشخیص زمان ایران برای پیام‌های هوشمند + شمارش معکوس تخفیف    | 🟢 پایین |     Timezone Service + Store API Sync     | نمایش صحیح زمان باقی‌مانده برای ۹۵٪ تخفیف‌های فعال |
| **استفاده از Refine+ Memory🔄**  | پشتیبانی کامل از `Intent: refine` با استفاده از تاریخچه مکالمه | ✅ تکمیل  | `LLMOrchestrator` + `ConversationMemory`  |    درک صحیح مرجع مقایسه در ۹۵٪ کوئری‌های refine    |
| **💬 ساختار Clarification Loop** |         پرسش هدایت‌گر هوشمند وقتی کوئری کاربر مبهم است         | 🔴 بالا  | NLU Confidence Score + Prompt Engineering | کاهش ۳۰٪ کوئری‌های `0 نتیجه` + افزایش رضایت کاربر  |
|      **🧠 Semantic Cache**       |    کش برداری کوئری‌های تکراری + TTL برای کاهش توکن و تأخیر     | 🔴 بالا  |        Qdrant + Embedding Service         |      کاهش ۴۰٪ مصرف توکن برای کوئری‌های تکراری      |
|   **👤 Personalization Lite**    |          ذخیره سلیقه کاربر + پیشنهاد مبتنی بر تاریخچه          | 🔴 بالا  |     Auth + PostgreSQL + Vector Memory     |  افزایش ۲۰٪ نرخ کلیک روی پیشنهادات شخصی‌سازی‌شده   |
|   **👍 بازخورد Like/Dislike**    |             ثبت بازخورد کاربر + یادگیری سبک سلیقه              | 🟡 متوسط |    Feedback Endpoint + Aggregator سبک     |           به‌روزرسانی خودکار JSON دامنه            |

### 📦 خروجی‌های مورد انتظار
- [ ] ماژول `SemanticCacheService` با پشتیبانی از TTL و Invalidation
- [ ] الگوی پرامپت `Clarification Prompt` در `PromptEngine` + لاجیک `confidence_threshold`
- [ ] جدول `user_preferences` در PostgreSQL + Endpoint `/api/v1/profile`
- [ ] به‌روزرسانی `LLMOrchestrator` برای تزریق `last_n_messages` به Context
- [ ] Endpoint `/api/v1/feedback` با Aggregator سبک + به‌روزرسانی خودکار آستانه‌ها/قواعد در YAML
- [ ] سرویس `TimeAwareService` با پشتیبانی از `Asia/Tehran`
- [ ] استانداردسازی پاسخ API

---

## 🔵 فاز Post-MVP 2: یکپارچه‌سازی فروشگاه
### 🎯 اهداف کلیدی
|              فیچر               |                              توضیح                               |  اولویت  |                  وابستگی‌ها                   |                      معیار موفقیت                       |
| :-----------------------------: | :--------------------------------------------------------------: | :------: | :-------------------------------------------: | :-----------------------------------------------------: |
|      **🛒 اتصال سبد خرید**      | افزودن محصول پیشنهادی به سبد خرید با OAuth 2.0 + Adapter Pattern | 🔴 بالا  |       فروشگاه باید API مستند ارائه دهد        |       امکان افزودن محصول با ۱ کلیک از پاسخ دستیار       |
|  **🔍 Intent: Compare Engine**  |         تولید جدول مقایسه‌ای یا متن تحلیلی بین ۲-۳ محصول         | 🟡 متوسط | `LLM Orchestrator` + Structured Output Schema |      تولید پاسخ مقایسه‌ای ساختاریافته در ۹۰٪ موارد      |
|       **💳 شرایط اقساط**        |           نمایش خودکار شرایط اقساط + محاسبه قسط ماهانه           | 🟡 متوسط |       Knowledge Base + Rule Engine سبک        |           پوشش ۱۰۰٪ محصولات دارای گزینه اقساط           |
| **📊 Analytics Dashboard Lite** |  گزارش «نیازهای پرجستجو»، «فیلترهای ناموفق»، «محصولات پربازدید»  | 🟡 متوسط |   Structured Logging + ClickHouse/Timescale   |        گزارش هفتگی خودکار برای تیم محصول فروشگاه        |
|   **🔍 تحلیل پیشرفته نظرات**    |           استخراج خودکار مزایا/معایب از نظرات کاربران            | 🟢 پایین |       Review Scraper + Lightweight LLM        | به‌روزرسانی خودکار `battery_quality` / `camera_quality` |


### 📦 خروجی‌های مورد انتظار
- [ ] `StoreAdapter` Interface + پیاده‌سازی Digikala
- [ ] ماژول `ComparePromptEngine` + Schema اعتبارسنجی پاسخ مقایسه‌ای
- [ ] ماژول `InstallmentCalculator` با قواعد قابل‌پیکربندی
- [ ] Dashboard ساده با Grafana یا Streamlit
- [ ] Job دوره‌ای `ReviewAnalyzer` با Rate Limit هوشمند

---

## 🔵 فاز Post-MVP 3: مقیاس‌پذیری فنی
### 🎯 اهداف کلیدی
|                 فیچر                 |                                توضیح                                 |  اولویت  |                  وابستگی‌ها                  |                          معیار موفقیت                           |
| :----------------------------------: | :------------------------------------------------------------------: | :------: | :------------------------------------------: | :-------------------------------------------------------------: |
|   **⚡ ONNX Export + Quantization**   |                    (کاهش ~۶۰٪ مصرف، Drift <0.002                     | ✅ تکمیل  |       `optimum[onnxruntime]` + تست دقت       |       کاهش Latency Embedding/Rerank به `<3s` (End-to-End)       |
| **🌍 Domain-Agnostic Prompt Engine** | سوئیچ آسان بین موبایل/هدفون/لپ‌تاپ با `base.yaml` و `{domain}.yaml`  | ✅ تکمیل  |   Refactor `PromptEngine` + Domain Router    |          افزودن دامنه جدید در `<1 ساعت` بدون تغییر کد           |
|        **📐 Evaluation Loop**        |        سنجش خودکار کیفیت با RAGAS / DeepEval + گزارش بنچمارک         | 🟡 متوسط |       Test Dataset + CI/CD Integration       |             جلوگیری از Regression در کیفیت پاسخ‌ها              |
|  **🕸️ Knowledge Graph (ارزیابی)**   |           بررسی Neo4j + Graph RAG برای استدلال چندمرحله‌ای           | 🟢 پایین |    Graph Schema Design + Query Benchmark     | اثبات برتری Graph RAG نسبت به Hybrid Search در سناریوهای پیچیده |
|       **🔄 Event-Driven Sync**       |         آپدیت لحظه‌ای قیمت/موجودی با Webhook + Message Queue         | 🟢 پایین | Store Webhook Support + Queue Infrastructure |      تاخیر آپدیت قیمت `<۵ دقیقه` از لحظه تغییر در فروشگاه       |
|      **🐳 Docker & Deployment**      | `docker-compose` برای Qdrant, Postgres, FastAPI + تنظیمات Production | 🟡 متوسط |       Dockerfile بهینه + Health Checks       |       استقرار یک‌خطی در محیط جدید با `docker-compose up`        |
|    **🎚️ تنظیم آستانه Reranking**    |   کالیبراسیون `min_score` در `RerankerService` بر اساس دادهٔ واقعی   | 🔴 بالا  |         لاگ‌های Reranking + تست A/B          |     کاهش نتایج نامرتبط در Top-3 بدون افزایش False Negative      |

### 📦 خروجی‌های مورد انتظار
- [x] به‌روزرسانی `_extract_slots` با پارسر کانفیگ‌محور + پشتیبانی از `brand_not`
- [x] لاجیک `relaxed_filters` و `_RELAXATION_ORDER` در `QdrantHybridRetriever`
- [x] الگوی `ConflictResolver` در `NLUPipeline` با اولویت‌بندی `price > brand > specs`
- [x] اتصال `Intent: refine` به `ConversationMemory` و تزریق `last_n_messages`
- [x] پایداری LLM JSON Parsing + Fallback Groq→Gemini + گارد تایپ
- [x]  `PromptEngine` + تمپلیت‌های YAML-Driven + تزریق پویا `ConfigDict` در Runtime
- [ ] ماژول `TokenMatcher` جایگزین Regex در `SlotExtractor`
- [ ] `DomainRouter` + Template System برای Promptهای پارامتریک
- [ ] GitHub Action برای اجرای خودکار `RAGAS` روی PRها
- [ ] PoC Graph RAG با Neo4j + مقایسه دقت/هزینه
- [ ] سرویس `SyncWorker` با پشتیبانی از Redis Streams
- [ ] `docker-compose.prod.yml` + `.env.example` + Health Check Endpoint
- [ ] اسکریپت `calibrate_reranker.py` برای یافتن `min_score` بهینه

---

## ⚠️ ریسک‌ها و راه‌کارهای کاهش
|                 ریسک                 |  احتمال  |  تأثیر   |                                         راه‌کار کاهش                                          |
| :----------------------------------: | :------: | :------: | :-------------------------------------------------------------------------------------------: |
|       وابستگی به API دیجی‌کالا       | 🟡 متوسط | 🔴 بالا  |                  طراحی `StoreAdapter` Interface از هم‌اکنون + Mock برای تست                   |
|      هزینهٔ APIهای LLM در مقیاس      | 🟡 متوسط | 🟡 متوسط |                       Semantic Cache + ONNX + Fallback به مدل سبک‌تر‫‫                        |
|   پیچیدگی شخصی‌سازی در مقیاس بزرگ    | 🔵 پایین | 🟡 متوسط |             شروع با `user_preferences` ساده + مهاجرت تدریجی به Vector DB جداگانه              |
|  نیاز به استدلال چندمرحله‌ای پیچیده  | 🔵 پایین | 🔴 بالا  |           ارزیابی Knowledge Graph فقط پس از جمع‌آوری دادهٔ کافی از کوئری‌های واقعی            |
|  پیچیدگی نگهداری Config در چنددامنه  | 🔵 پایین | ✅ تکمیل  | مهاجرت به YAML ماژولار + TokenParser. افزودن دامنه‌های جدید فقط نیاز به تعریف فایل جدید دارد. |
| تأخیر ناشی از Fallbackهای متوالی LLM | 🔵 پایین | 🟡 متوسط |                    کاهش `max_retries` + Timeout سخت‌گیرانه + Log Analysis                     |
