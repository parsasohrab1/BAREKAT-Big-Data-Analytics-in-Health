# BAREKAT - Big Data Analytics in Health

پلتفرم تحلیل کلان‌داده سلامت برای پردازش و تحلیل داده‌های حجیم و ناهمگن از منابع مختلف (EHR، دستگاه‌های پوشیدنی، تصاویر پزشکی، داده‌های ژنومی).

## معماری زیرساخت

```
┌─────────────┐    ┌──────────┐    ┌─────────────┐
│  CSV/HL7/   │───▶│   ETL    │───▶│ PostgreSQL  │
│  DICOM      │    │ Pipeline │    │ (Warehouse) │
└─────────────┘    └──────────┘    └─────────────┘
       │                │                  │
       ▼                ▼                  ▼
┌─────────────┐    ┌──────────┐    ┌─────────────┐
│   MinIO     │    │  Kafka   │    │  Analytics  │
│ (Object)    │    │(Streaming)│   │   Schema    │
└─────────────┘    └──────────┘    └─────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
┌─────────────┐    ┌──────────┐    ┌─────────────┐
│   Spark     │    │ FastAPI  │    │  Streamlit  │
│ (Processing)│    │  (API)   │    │ (Dashboard) │
└─────────────┘    └──────────┘    └─────────────┘
```

### سرویس‌ها

| سرویس | پورت | نقش |
|--------|------|-----|
| PostgreSQL | 5432 | انبار داده (Data Warehouse) |
| MinIO | 9000/9001 | ذخیره‌سازی فایل (DICOM, HL7, CSV) |
| Redis | 6379 | کش و session |
| Kafka | 9092 | پردازش جریانی رویدادها |
| Spark | 7077/8080 | پردازش توزیع‌شده |
| API | 8000 | REST API با RBAC |
| Dashboard | 8501 | داشبورد تحلیلی |

## راه‌اندازی سریع

### پیش‌نیازها

- Python 3.11+
- Docker & Docker Compose
- Make (اختیاری)

### نصب

```bash
# 1. کلون و نصب وابستگی‌ها
cp .env.example .env
pip install -r requirements.txt
pip install -e .

# 2. راه‌اندازی زیرساخت Docker
docker compose up -d postgres minio redis

# 3. تولید داده سنتتیک
python scripts/generate_data.py --patients 1000 --admissions 3000

# 4. اجرای ETL
python -m barekat.etl.pipeline

# 5. آموزش مدل‌های ML
python -m barekat.ml.pipeline

# 6. راه‌اندازی API
uvicorn barekat.api.main:app --reload --port 8000

# 7. داشبورد
streamlit run dashboards/app.py
```

### با Makefile

```bash
make setup          # نصب وابستگی‌ها
make infra          # سرویس‌های Docker
make generate-data  # تولید داده
make etl            # خط لوله ETL
make train          # آموزش ML
make api            # API سرور
make dashboard      # داشبورد
make test           # تست‌ها
```

## ساختار پروژه

```
├── docker/              # تنظیمات Docker
│   ├── postgres/        # Schema پایگاه داده
│   ├── api/             # Dockerfile API
│   └── dashboard/       # Dockerfile داشبورد
├── src/barekat/         # کد اصلی
│   ├── api/             # FastAPI endpoints
│   ├── config/          # تنظیمات
│   ├── etl/             # خط لوله ETL
│   ├── ingestion/       # بارگذاری CSV/HL7/DICOM
│   ├── ml/              # مدل‌های ML
│   ├── security/        # احراز هویت و RBAC
│   └── storage/         # PostgreSQL, MinIO, Redis, Kafka
├── scripts/             # اسکریپت‌های کمکی
├── dashboards/          # داشبورد حرفه‌ای Streamlit
│   ├── app.py           # نقطه ورود داشبورد
│   ├── pages/           # صفحات تحلیلی
│   └── utils/           # بارگذاری داده، نمودار، ML
├── data/                # داده‌های خام و پردازش‌شده
└── tests/               # تست‌ها
```

## API

مستندات API: `http://localhost:8000/docs`

### احراز هویت

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### نقش‌های کاربری (RBAC)

| نقش | دسترسی‌ها |
|-----|-----------|
| admin | مدیریت کامل، ETL، کاربران |
| clinician | مشاهده PHI، هشدارها |
| researcher | تحلیل، export |
| viewer | فقط خواندن |

## امنیت و حریم خصوصی

- احراز هویت JWT
- کنترل دسترسی مبتنی بر نقش (RBAC)
- لاگ دسترسی در schema `audit`
- رمزنگاری ارتباطات (TLS در production)

## تولید داده سنتتیک

اسکریپت اصلی: `scripts/generate_data.py` (نسخه قبلی: `scripts/original_DATA.py`)

جداول: Patients, Admissions, Diagnoses, Medications, Lab_Results

## داشبورد تحلیلی

داشبورد حرفه‌ای Streamlit در `dashboards/app.py` تمام قابلیت‌های پلتفرم را نمایش می‌دهد.

**آدرس:** `http://localhost:8501`

### صفحات داشبورد

| صفحه | محتوا |
|------|--------|
| نمای کلی | KPIها، gaugeها، روند بستری، جدول بستری‌های اخیر |
| جمعیت بیماران | سن، BMI، دیابت، فشارخون، سیگار، گروه خونی |
| بستری و بخش‌ها | توزیع بخش، LOS، ICU، نوع پذیرش |
| تشخیص‌ها | ICD-10، تشخیص اصلی/فرعی، نقشه تشخیص-بخش |
| داروها | داروهای پرتجویز، فرکانس مصرف، نقشه دارویی |
| آزمایشگاه | نتایج غیرطبیعی، توزیع تست‌ها، هیستوگرام |
| هوش تحلیلی ML | پیش‌بینی بستری مجدد، خوشه‌بندی، اهمیت ویژگی |
| هشدارها | هشدارهای ریسک با سطح شدت و دانلود CSV |
| زیرساخت | وضعیت داده، معماری، کیفیت داده، قابلیت‌ها |

### فیلترهای سراسری

از سایدبار می‌توانید بر اساس **بخش**، **جنسیت** و **نوع پذیرش** فیلتر کنید.

### اجرا

```bash
# تولید داده (در صورت نیاز)
python scripts/generate_data.py --patients 1000 --admissions 3000

# اجرای داشبورد
streamlit run dashboards/app.py
```
