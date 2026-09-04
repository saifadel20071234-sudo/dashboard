# ⚡ PowerStep Grid — Dashboard

> لوحة التحكم الحية لنظام PowerStep Grid — نظام توليد الطاقة الذكي من خطوات المشاة.

---

## 📁 هيكل الملفات

```
dashboard/
├── index.html              # الهيكل الأساسي للداش بورد (HTML فقط)
├── style.css               # جميع الأنماط والتصميم (CSS)
├── app.js                  # المنطق والتحديثات اللحظية (JavaScript)
├── dashboard_data.json     # بيانات الداش بورد (Data Structure)
├── manifest.json           # إعدادات PWA
├── sw.js                   # Service Worker
├── icon-192.png            # أيقونة 192x192
├── icon-512.png            # أيقونة 512x512
└── vendor/
    ├── chart.umd.js        # مكتبة Chart.js للرسوم البيانية
    └── fonts/
        └── Cairo-Regular.ttf   # خط Cairo العربي
```

---

## 🛠️ التقنيات المستخدمة

| التقنية | الاستخدام |
|---|---|
| HTML5 | هيكل الصفحة |
| CSS3 | التصميم (Glassmorphism + Sci-Fi Theme) |
| JavaScript (Vanilla) | المنطق + WebSocket + Real-time Updates |
| Chart.js | الرسوم البيانية (توليد vs استهلاك) |
| Web Audio API | المؤثرات الصوتية |
| PWA | دعم التطبيق كـ Progressive Web App |

---

## 📊 البيانات (`dashboard_data.json`)

الملف ده فيه شكل الداتا اللي الداش بورد بيستخدمها:

### `live` — البيانات اللحظية
- `generation_w` — التوليد اللحظي (واط)
- `consumption_w` — الاستهلاك اللحظي (واط)
- `forecast_w` — توقع الـ AI
- `self_sufficiency_pct` — نسبة الاكتفاء الذاتي
- `storage_soc_pct` — نسبة شحن البطارية
- `footfall` — عدد الخطوات/دقيقة
- `loads` — حالة الأحمال
- `alerts` — التنبيهات
- `tiles` — حالة البلاطات (16 بلاطة)

### `history` — البيانات التراكمية (للرسم البياني)
- `t` — الساعات
- `gen_wh` / `con_wh` — التوليد والاستهلاك
- `soc_wh` — شحن البطارية
- `footfall` — معدل الحركة

---

## 👥 الفريق

| العضو | المسؤولية |
|---|---|
| **سيف عادل** | Dashboard (لوحة التحكم) |

---

## 🚀 التشغيل

افتح `index.html` في المتصفح مباشرة، أو شغّل مع Backend Server:

```bash
# من مجلد backend في المشروع الرئيسي
uvicorn app:app --reload --port 8000
```

---

© 2026 PowerStep Grid Team