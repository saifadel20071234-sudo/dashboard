# PowerStep Dashboard — نظام الداش بورد + باك إند حقيقي

هذا المشروع يربط **داش بورد عربي** (واجهة تحكم) بنظام الفريق الحقيقي (قراءات البيزو + ESP32 عبر `main_system.py`)، بحيث:

- الداش بورد يعرض **بيانات حقيقية فقط** من الأجهزة (بيزو + ESP32) — لا يوجد أي simulation أو fake data.
- تشغيل واحد (`Start_Dashboard.bat`) يفتح النظام + الواجهة معاً.
- التنبيهات (بطارية منخفضة، انقطاع جهاز، ازدحام…) تُعرض من قاعدة البيانات الحقيقية.

---

## 1) البنية (Architecture)

```
ESP32 (WiFi) ── POST /api/ingest ──> Flask main_system.py (:8000)
Piezo (Serial COM6) ─────────────> main_system.py (thread قراءة سيريال)
                                    │
                    متبقى pipeline الجهاز: inference → database → alerts
                                    │
                    dashboard_bridge.py (فوق نفس الـ Flask)
                                    │
        WebSocket /ws/live + /api/history + /api/analytics/summary + /api/export/csv
                                    │
                     Frontend Dashboard (:5500) http.server
```

**كل شيء في السيرفر نفسه**: `main_system.py` يشغّل Flask على المنفذ `8000`، و`dashboard_bridge.py` تُركّب على نفس الـ app فتحسب سطر واحد فقط.

---

## 2) هيكل المجلدات

```
dashboard/
├── index.html, app.js, style.css   ← الداش بورد (واجهة واحدة، خريطة ممر 16 بلاطة)
├── analytics.html                    ← صفحة تحليل (رسم بياني)
├── API_SPEC.md                       ← عقد الـ API بين الباك إند والواجهة (لا تغيّر أسماء الحقول)
├── Start_Dashboard.bat               ← مشغل كل شيء
└── backend/
    ├── main_system.py                ← نقطة الدخول الحقيقية (كود الفريق + 3 hooks صغيرة)
    ├── config.py                     ← كل المسارات/المنافذ/الحدود (من نظام الفريق)
    ├── database_manager.py           ← SQLite (من نظام الفريق)
    ├── realtime_inference.py         ← تحميل موديلات AI والتنبؤ (من نظام الفريق)
    ├── alert_manager.py              ← التنبيهات (تيليجرام/إيميل/صافر) (من نظام الفريق)
    ├── dashboard_bridge.py           ← جسر الداش بورد (WebSocket + REST + CORS) [إضافة لنا]
    ├── simulate_wifi_traffic.py      ← إعادة تشغيل بيانات WiFi حقيقية تاريخية (اختبار فقط)
    ├── train_peak_forecast_model.py  ← تدريب موديل توقع الإشغال (اختياري)
    └── requirements.txt              ← الحزم بالنسخ المحددة
```

> ملاحظة: كل موديولات `backend/` هي نسخة طبق الأصل من موديولات الفريق في مجلد `hhh/` — لم تُعدَّل إلا:

- `config.py`: أُضيف `MODELS_DIR` متغير بيئة (اختياري).
- `realtime_inference.py`: أصبح يتحمّل الموديلات بمرونة (لو ملف عداد غير موجود لا ينهار النظام، ويعمل تلقائياً عند ظهور الملف).
- `main_system.py`: أُضيفت **4 أسطر فقط** لربط الجسر (انظر القسم 6).

---

## 3) المتطلبات والتشغيل

### 3.1 تثبيت الحزم (مرة واحدة)

```bash
cd backend
pip install -r requirements.txt
```

الحزم المحددة: `flask==3.1.3`, `pyserial==3.5`, `pandas==3.0.2`, `numpy==2.4.4`, `scikit-learn==1.9.0`, `xgboost==3.4.1`, `joblib==1.5.3`, `requests`, `python-dotenv`, `flask-sock`, `flask-cors`.

### 3.2 التشغيل

**الطريقة الأسهل (موصى بها):**

```bash
Start_Dashboard.bat
```

- يفتح نافذة «PowerStep Backend» → `main_system.py` على `:8000`
- يفتح نافذة «PowerStep Frontend» → `http.server` على `:5500`
- يفتح المتصفح على `http://localhost:5500/`

**يدوياً:**
```bash
# نافذة 1
cd backend && python main_system.py     # :8000

# نافذة 2
python -m http.server 5500              # :5500
```

---

## 4) موديلات الذكاء الاصطناعي (مهم جداً)

النظام الحقيقي (من الفريق) يعتمد على **4 موديلات** جاهزة `.joblib` داخل مجلد اسمه بالظبط:

```
backend/data cleaning and AI models/
├── piezo_step_model.joblib            # كشف خطوة البيزو (Voltage, Power)
├── wifi_occupancy_model.joblib        # هل المكان مشغول؟ (csi_variance)
├── wifi_count_model.joblib            # عدد الأشخاص (device_count_raw)
├── peak_forecast_model_1st.joblib     # توقّع الإشغال حسب الوقت (hour, minute, day_of_week)
└── university_simulated_week_1st.csv  # ملف التدريب المرجعي
```

**الوضع الحالي**: هذه الملفات **ليست داخل الريبو** (غير مرفوعة لصغرها/لأنها مملوكة لجهة أخرى). النتائج:

| الحالة | ماذا يحدث |
|---|---|
| الموديلات موجودة في المجلد | الـ AI يعمل كاملاً (كشف خطوات، إشغال، عدد أشخاص، توقعات، تنبيهات mismatch) |
| الموديلات غير موجودة | النظام **لا ينهار** — يعمل بالبيانات الخام من الأجهزة فقط، وكشف الخطوات يقتصر على `footfall` الفيرموير، وستظهر تحذيرات "Model file not found" في اللوج |

**لو الموديلات معاك**: ضع المجلد داخل `backend/` بالاسم تماماً، أو حدد مكانه بدون تعديل كود عبر:

```bash
set MODELS_DIR=C:\path\to\models
```

عند توفر الملفات فعلاً، يتم تحميلها تلقائياً عند الإقلاع.

> ملاحظة: `wifi_occupancy_model` يميل للتوقّع "مشغول" حتى عند `csi_variance` منخفض، لأن بيانات تدريبه أغلبها مشغول. هذا خاصّة في بيانات التدريب وليست خطأ — ولهذا يوجد `mismatch_flag` لإظهار الخلاف بين النموذج والفيرموير.

---

## 5) إعدادات الأجهزة والتخصيص (بلا تعديل كود)

كل قيم `config.py` قابلة للتخصيص عبر `.env` أو متغيرات بيئة.

| المفتاح | الافتراضي | الوصف |
|---|---|---|
| `PIEZO_SERIAL_PORT` | `COM6` | منفذ البيزو (على ويندوز `COM6`، على لينكس مثل `/dev/ttyUSB0`) |
| `PIEZO_BAUD_RATE` | `115200` | سرعة السيريال (ثابتة في فيرموير ae8.ino) |
| `WIFI_INGEST_PORT` | `8000` | منفذ استقبال الـ ESP32 (مثبت في الفيرموير — لا تغيّره) |
| `WIFI_NODE_ID` | `corridor_node_1` | اسم عقدة الـ WiFi |
| `MODELS_DIR` | `backend/data cleaning and AI models` | مكان مجلد الموديلات |
| `OCCUPANCY_ALERT_THRESHOLD` | `6` | حد التنبيه عن الزحام |
| `LOW_BATTERY_SOC_THRESHOLD` | `15.0` | حد إنذار البطارية المنخفضة |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | فارغ | لتشغيل تنبيهات تيليجرام |
| `SMTP_*` | فارغ | لتشغيل تنبيهات الإيميل |

مثال `.env` في جذر `backend/`:
```
PIEZO_SERIAL_PORT=COM6
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=yyy
```

---

## 6) كيف يرتبط الداش بورد بالنظام؟ (الـ bridge)

الملف `backend/main_system.py` (نسخة الفريق) أُضيفت له **4 أسطر فقط** بدون تغيير أي منطق:

| السطر | الموقع | الوظيفة |
|---|---|---|
| `from dashboard_bridge import get_bridge` | أعلى الملف | استيراد الجسر |
| `get_bridge().on_piezo(record)` | داخل `_read_loop` بعد معالجة قراءة البيزو | تمرير القراءة للداش بورد |
| `get_bridge().on_wifi(record)` | داخل `/api/ingest` بعد المعالجة | تمرير قراءة الـ ESP32 للداش بورد |
| `get_bridge().attach(app).set_db(db)` | داخل `create_app` | تركيب الجسر على Flask + تمرير قاعدة البيانات (لقراءة التنبيهات الحقيقية) |

### نقاط الوصل (Endpoints) المقدمة من `dashboard_bridge.py`

| المسار | النوع | الوصف |
|---|---|---|
| `/ws/live` | WebSocket | بث بيانات حية كل ثانية (بنفس schema الـ API_SPEC) |
| `/api/history` | GET | تاريخ للرسم البياني (من فترة كل 4 ثوانٍ) |
| `/api/analytics/summary` | GET | ملخص إحصائيات للصفحة التحليلية |
| `/api/export/csv` | GET | نزيل CSV للبيانات |

اتّفاق الحقول كاملاً في [`API_SPEC.md`](API_SPEC.md) — **لا تغيّر أسماء الحقول** أو الواجهة ستتعطل.

> **مبدأ إلزامي**: الجسر لا يولّد أي بيانات صناعية إطلاقاً. كل قيمة في الرسالة قادمة من قراءة حقيقية (بيزو أو ESP32). الوحدات من الموديولات الحقيقية مثل `generation_w`, `final_people_count`, `ai_step_detected`, `received_at`.

---

## 7) اختبار النظام من غير أجهزة (اختباري فقط)

لتجربة المسار الكامل دون توصيل أجهزة، استخدم البيانات التاريخية الحقيقية:

**الطريقة 1 — محاكاة WiFi (من نظام الفريق):**
```bash
# نافذة 1
cd backend && python main_system.py
# نافذة 2
python backend/simulate_wifi_traffic.py --interval 2 --count 50
# تحقق
curl http://localhost:8000/api/status
```

**الطريقة 2 — سيرفر تطوير محلي** (`backend/dev_test_server.py`):
يغذي الواجهة ببيانات حقيقية تاريخية من CSV (لا ينصح به للإنتاج، للتطوير فقط):
```bash
python backend/dev_test_server.py   # يعمل على :8001
```

---

## 8) التنبيهات (AlertManager)

المنبهات تُطلق عند:
- زحام فوق `OCCUPANCY_ALERT_THRESHOLD`
- بطارية منخفضة تحت `LOW_BATTERY_SOC_THRESHOLD`
- انخفاض مفاجئ في التوليد مع استمرار الضغط (خطأ محتمل في البلاطة)
- خلاف مستمر بين النموذج والفيرموير (mismatch)
- انقطاع أحد القنوات (بيزو/ WiFi) — watchdog

كل تنبيه يُسجَّل في `alerts_log` بالقاعدة حتى بدون إعداد قنوات الإرسال، ويُعرض في الداش بورد تلقائياً.

---

## 9) أخطاء شائعة

| المشكلة | الحل |
|---|---|
| «Address already in use» على `:8000` | نظام قديمة شغالة. أغلقها (مثلاً أوقف العملية على المنفذ) ثم أعد التشغيل |
| تحذير "Model file not found" | الموديلات غير موجودة — يعمل النظام عادي (القسم 4) |
| البيزو لا يقرأ | تأكد أن الجهاز على `PIEZO_SERIAL_PORT` الصحيح، وسرعة السيريال 115200 |
| الواجهة مفتوحة لكن «CONNECTION LOST» | تأكد أن `main_system.py` شغال على `:8000` (نافذة Backend) |
| `pyserial` غير مثبت | لا يتوقف مسار ESP32 إلا أن البيزو يتوقف. ثبّت: `pip install pyserial` |

---

## 10) git / النشر

```bash
git clone https://github.com/saifadel20071234-sudo/dashboard.git
cd dashboard
# ثم اتبع القسم 3 (تثبيت + تشغيل)
```

ملاحظات:
- `backend/runtime_data/` و `backend/logs/` مستثناة من git (تُنشأ تلقائياً عند التشغيل).
- لا ترفع أبداً `.env` أو أي مفاتيح/رموز.
- الموديلات `.joblib` غير مرفوعة بالتصميم — تُمرر بأمان خارج الريبو أو عبر `MODELS_DIR`.

---

## الأسئلة / التواصل

قبل تغيير أي اسم حقل في `API_SPEC.md` أو الباك إند، تواصل مع مسؤول الداش بورد — الواجهة تقرأ الحقول حرفياً بدون أي مرونة.