# BAREKAT - Big Data Analytics in Health

پلتفرم تحلیل کلان‌داده سلامت برای پردازش و تحلیل داده‌های EHR، آزمایشگاه، تصاویر پزشکی (DICOM) و رویدادهای بالینی بلادرنگ (HL7/FHIR).

> **Roadmap:** داده ژنومیک و دستگاه‌های پوشیدنی در نسخه فعلی پیاده‌سازی نشده‌اند.

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

# 4. اجرای ETL (incremental - پیش‌فرض)
python -m barekat.etl.pipeline --mode incremental

# یا بارگذاری کامل
python -m barekat.etl.pipeline --mode full

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
make etl            # ETL incremental
make etl-full       # ETL full reload
make worker         # Celery worker
make beat           # Celery Beat scheduler
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
│   ├── etl/             # خط لوله ETL + validation + incremental
│   ├── worker/          # Celery Beat scheduling
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

ورود از جدول `audit.users` با bcrypt انجام می‌شود. در production مقدار `AUTH_DEV_FALLBACK=false` باشد.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Migration خودکار

Migrationهای `docker/postgres/migrations/002` تا `013` به‌صورت خودکار در startup API (`DB_AUTO_MIGRATE=true`) یا با دستور زیر اعمال می‌شوند:

```bash
make db-migrate
# یا
python scripts/apply_init_sql.py   # init.sql + همه migrationها (CI/تست)
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

## ETL پیشرفته

### زمان‌بندی خودکار (Celery Beat)

```bash
# Docker
docker compose up -d celery-worker celery-beat

# Local
make worker   # ترمینال ۱
make beat     # ترمینال ۲
```

| Job | زمان‌بندی | حالت |
|-----|----------|------|
| `etl-incremental-hourly` | هر ساعت | incremental |
| `etl-full-daily` | روزانه ساعت ۲ | full reload |

### اعتبارسنجی Schema (Great Expectations)

قبل از بارگذاری، هر جدول با Great Expectations اعتبارسنجی می‌شود (null checks، محدوده سنی، یکتایی PK). در صورت شکست، ETL متوقف و در `audit.etl_runs` ثبت می‌شود.

```bash
python -m barekat.etl.pipeline --mode incremental
python -m barekat.etl.pipeline --mode full --skip-validation  # فقط توسعه
```

### بارگذاری Incremental

- رکوردهای جدید: `INSERT`
- رکوردهای موجود: `UPSERT` (ON CONFLICT)
- watermark در `staging.etl_watermarks`
- حالت `full`: `TRUNCATE` + بارگذاری مجدد

### لاگ اجرا و Retry

هر اجرا در `audit.etl_runs` ثبت می‌شود:

```bash
# API
GET /api/v1/analytics/etl/runs

# داشبورد → صفحه زیرساخت
```

Celery در صورت خطا تا ۳ بار (قابل تنظیم) retry می‌کند.

## MLOps

### نسخه‌بندی مدل و متریک‌ها

هر آموزش در `analytics.ml_model_registry` ثبت می‌شود:

- نسخه (`v20260713_003000`)
- artifact در `data/models/{model_name}/{version}/`
- متریک‌ها: AUC، F1، precision، recall، Brier score
- داده calibration (reliability diagram)

```bash
python -m barekat.ml.pipeline
python -m barekat.ml.pipeline --retrain   # داده جدید از PostgreSQL
```

### مدل‌های پیشرفته

| مدل | کاربرد | API |
|-----|--------|-----|
| **LOS** | برنامه‌ریزی تخت | `GET /api/v1/ml/predict/los` |
| **مرگ‌ومیر / سپسیس** | هشدار زودهنگام | `GET /api/v1/ml/predict/early-warning` |
| **NLP یادداشت پزشک** | استخراج تشخیص ICD | `POST /api/v1/ml/nlp/extract-diagnoses` |
| **علائم حیاتی (time-series)** | مانیتورینگ لحظه‌ای | `GET /api/v1/ml/vitals/monitor/{admission_id}` |

داده‌های جدید: `clinical_notes.csv`, `vital_signs.csv` + فیلدهای `Mortality_Flag`, `Sepsis_Flag` در admissions.

```bash
python scripts/generate_data.py --patients 1000 --admissions 3000
python -m barekat.ml.pipeline   # آموزش همه مدل‌ها + تولید هشدار
```

### API مدل

| Endpoint | نقش |
|----------|-----|
| `POST /api/v1/ml/train` | آموزش |
| `POST /api/v1/ml/retrain` | retrain با داده جدید |
| `GET /api/v1/ml/models` | لیست نسخه‌ها |
| `GET /api/v1/ml/models/readmission/metrics` | متریک‌ها و calibration |
| `GET /api/v1/ml/predict/readmission/explain/{admission_id}` | توضیح SHAP — چرا پرخطر؟ |
| `GET /api/v1/ml/predict/readmission/report/{admission_id}` | گزارش HTML قابل چاپ |
| `GET /api/v1/ml/thresholds` | آستانه per-department |
| `PUT /api/v1/ml/thresholds/{department}` | تنظیم آستانه |

### آستانه ریسک per-department

جدول `analytics.department_risk_thresholds` — هر بخش آستانه جداگانه دارد (مثلاً Cardiology: 0.75، Pediatrics: 0.65).

### Retrain دوره‌ای

Celery Beat job `ml-retrain-weekly` — هر دوشنبه ساعت ۳ صبح (قابل تنظیم):

```env
ML_RETRAIN_DAY_OF_WEEK=0
ML_RETRAIN_HOUR=3
```

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
| مدیریت مراکز | سوییچ tenant، quota، billing، تنظیمات برندینگ (platform admin) |
| گزارش‌های مدیریتی | گزارش هفتگی PDF/Excel، تنظیمات ایمیل/پیامک |
| زیرساخت | وضعیت داده، معماری، کیفیت داده، قابلیت‌ها |

### فیلترهای سراسری

از سایدبار می‌توانید بر اساس **بخش**، **جنسیت** و **نوع پذیرش** فیلتر کنید.

### احراز هویت داشبورد

داشبورد با JWT و RBAC محافظت می‌شود. پس از ورود، صفحات بر اساس نقش نمایش داده می‌شوند.

| کاربر | رمز | نقش | مرکز |
|-------|-----|-----|------|
| admin | admin123 | دسترسی کامل (platform admin) | default |
| clinician | clinician123 | PHI + تأیید هشدار | tehran-general |
| researcher | researcher123 | تحلیل و ML | isfahan-medical |

### منبع داده

پس از ETL، داشبورد به‌صورت خودکار از **PostgreSQL** می‌خواند (`DASHBOARD_DATA_SOURCE=auto`).

```bash
# 1. تولید داده
python scripts/generate_data.py --patients 1000 --admissions 3000

# 2. ETL به PostgreSQL
python -m barekat.etl.pipeline

# 3. ML + ذخیره هشدارها در analytics.predictive_alerts
python -m barekat.ml.pipeline

# 4. اجرای داشبورد
streamlit run dashboards/app.py
```

### هشدارهای واقعی

هشدارها پس از `python -m barekat.ml.pipeline` در جدول `analytics.predictive_alerts` ذخیره می‌شوند و در صفحه **هشدارها** نمایش داده می‌شوند. نقش `clinician` و `admin` می‌توانند هشدار را تأیید کنند.

streamlit run dashboards/app.py
```

## تصاویر پزشکی (DICOM / PACS)

علاوه بر metadata، اکنون اتصال PACS، thumbnail و viewer فعال است.

```
PACS (C-ECHO/C-FIND یا Orthanc REST)
        ↓ retrieve
   MinIO (dicom/*.dcm + thumbnails)
        ↓
   raw.dicom_studies + Dashboard Viewer
        ↓ (فاز بعد)
   CAD — تشخیص کمکی
```

### API (`/api/v1/imaging`)

| Endpoint | کاربرد |
|----------|--------|
| `POST /pacs/echo` | تست اتصال PACS (C-ECHO) |
| `POST /pacs/query` | جستجوی مطالعات (C-FIND / Orthanc) |
| `POST /pacs/retrieve` | دریافت study از PACS → MinIO |
| `POST /upload` | آپلود فایل `.dcm` |
| `GET /studies` | کاتالوگ مطالعات |
| `GET /studies/{uid}/thumbnail` | PNG thumbnail |
| `GET /studies/{uid}/viewer?window=&level=` | تصویر viewer با Window/Level |
| `GET /studies/{uid}/cad` | CAD stub (فاز بعد) |

### راه‌اندازی

```bash
# تولید DICOM نمونه
python scripts/generate_sample_dicom.py --output ./data/dicom --count 5

# ingest به MinIO + PostgreSQL
python -c "from pathlib import Path; from barekat.imaging.store import ingest_directory; ingest_directory(Path('./data/dicom'))"

# داشبورد → صفحه «تصاویر پزشکی»
streamlit run dashboards/app.py
```

### تنظیمات PACS (`.env`)

```env
PACS_HOST=localhost
PACS_PORT=4242
PACS_AE_TITLE=ORTHANC
PACS_ORTHANC_URL=http://localhost:8042
```

### CAD — فاز بعد

مدل‌های برنامه‌ریزی‌شده: Chest X-ray (pneumothorax), CT (hemorrhage/PE), Mammography (mass).  
فعلاً `CADAnalyzer` فقط stub برمی‌گرداند — برای تحقیق و توسعه، نه استفاده بالینی.

## انطباق و حریم خصوصی (HIPAA / GDPR / قوانین داخلی)

```
درخواست API / داشبورد
        ↓ AuditMiddleware
   audit.access_logs (چه کسی، چه زمانی، به چه داده‌ای)
        ↓
   RBAC + view_phi (حداقل ضرورت)
        ↓
   Retention Celery Beat → حذف خودکار داده منقضی
```

### چارچوب‌های پشتیبانی‌شده

| چارچوب | پوشش |
|--------|------|
| **HIPAA** | RBAC، audit trail، minimum necessary، de-identification |
| **GDPR** | رضایت، حق حذف (erasure)، pseudonymization، retention |
| **قوانین داخلی** | SEPAS، کد ملی (عدم ذخیره در analytics)، مصوبات وزارت بهداشت |

### API (`/api/v1/compliance`)

| Endpoint | کاربرد |
|----------|--------|
| `GET /frameworks` | چارچوب‌های قانونی فعال |
| `GET /summary` | خلاصه پوشش انطباق (admin) |
| `GET /audit-logs` | لاگ دسترسی کامل |
| `POST /pseudonymize/{id}` | شناسه‌سازی مجدد (reversible) |
| `POST /anonymize/{id}` | ناشناس‌سازی (غیرقابل بازگشت) |
| `POST /erasure/{id}` | حق حذف GDPR |
| `GET /retention/policies` | سیاست نگهداری |
| `POST /retention/purge` | حذف دستی داده منقضی |
| `POST /consent` | ثبت رضایت‌نامه |
| `POST /legal-hold` | توقیف قانونی (توقف حذف) |
| `GET /export/deidentified` | خروجی تحقیقاتی de-ID |

### سیاست نگهداری پیش‌فرض

| دسته داده | مدت | مرجع |
|-----------|-----|------|
| یادداشت بالینی | ۷ سال | HIPAA/GDPR/IR-MOH |
| نتایج آزمایش | ۵ سال | HIPAA |
| تصاویر DICOM | ۱۰ سال | IR-MOH |
| لاگ دسترسی | ۶ سال | HIPAA/GDPR |

### تنظیمات (`.env`)

```env
AUDIT_ENABLED=true
AUDIT_LOG_IP=true
COMPLIANCE_FRAMEWORK=all
PSEUDONYMIZATION_SALT=change-me-pseudonym-salt
DATA_RETENTION_ENABLED=true
RETENTION_PURGE_HOUR=4
REQUIRE_CONSENT_FOR_RESEARCH=false
```

داشبورد → صفحه **«انطباق و حریم خصوصی»** (فقط admin).

## امنیت زیرساخت (TLS / Secrets / MFA / WAF)

```
Client ──TLS──► Nginx (WAF + rate limit)
                    ├── api.barekat.local      → API
                    ├── dashboard.barekat.local → Streamlit
                    └── minio.barekat.local    → MinIO (SSE)

Secrets: Docker Secrets (/run/secrets/*) یا HashiCorp Vault
PHI at-rest: Fernet encryption (clinical_notes) + MinIO KMS
Admin MFA: TOTP (Google Authenticator / Authy)
```

### راه‌اندازی Secure Stack

```bash
make secrets      # تولید فایل‌های secret در ./secrets/
make tls-certs    # گواهی self-signed TLS
make secure-up    # prod + docker-compose.secure.yml
```

### Docker Secrets (جایگزین .env)

| Secret | مسیر |
|--------|------|
| `jwt_secret` | `/run/secrets/jwt_secret` |
| `postgres_password` | `/run/secrets/postgres_password` |
| `phi_encryption_key` | `/run/secrets/phi_encryption_key` |
| `minio_secret_key` | `/run/secrets/minio_secret_key` |

Vault (اختیاری): `VAULT_ADDR` + `VAULT_TOKEN` → KV path `barekat`

### MFA برای Admin

```bash
# 1. Login as admin
# 2. POST /api/v1/auth/mfa/enroll  → QR code
# 3. POST /api/v1/auth/mfa/activate {"code": "123456"}
# 4. Login → mfa_token → POST /api/v1/auth/mfa/verify
```

### Rate Limiting & WAF

| لایه | محافظت |
|------|--------|
| **Nginx** | `limit_req`, bad-bot block, SQLi/XSS در query string |
| **FastAPI** | Redis rate limit (120/min API, 10/min login) |
| **SecurityMiddleware** | WAF patterns, HSTS, CSP, X-Frame-Options |

### رمزنگاری PHI at-rest

```bash
# فعال‌سازی
PHI_ENCRYPTION_ENABLED=true
PHI_ENCRYPTION_KEY_FILE=/run/secrets/phi_encryption_key

# رمزنگاری یادداشت‌های موجود
POST /api/v1/compliance/phi/encrypt
```

## چندمستاجری (Multi-Tenancy)

پلتفرم از چند بیمارستان/مرکز درمانی به‌صورت همزمان پشتیبانی می‌کند:

| قابلیت | توضیح |
|--------|--------|
| **جداسازی داده** | ستون `tenant_id` روی جداول `raw.*` و `analytics.*` + فیلتر خودکار در API و داشبورد |
| **تنظیمات اختصاصی** | لوگو، رنگ اصلی، locale، timezone، صفحات فعال per-tenant |
| **داشبورد اختصاصی** | برندینگ سایدبار و کش داده per-tenant |
| **Billing & Quota** | پلن (starter/pro/enterprise)، سقف بیمار/API/ذخیره‌سازی، metering روزانه |

### Schema

```
tenant.tenants          — مراکز (slug, plan, status)
tenant.plans            — starter / pro / enterprise
tenant.tenant_settings  — برندینگ و تنظیمات UI
tenant.tenant_users     — نگاشت کاربر → tenant
tenant.usage_records    — مصرف API (metering)
tenant.usage_summary    — خلاصه روزانه
```

### Migration

```bash
# پس از راه‌اندازی PostgreSQL
psql $DATABASE_URL -f docker/postgres/migrations/009_multi_tenancy.sql
```

مراکز نمونه: `default`, `tehran-general`, `isfahan-medical`, `mashhad-university`

### احراز هویت و Context

JWT شامل `tenant_id` و `tenant_slug` است. Platform admin می‌تواند با هدر `X-Tenant-ID` بین مراکز جابه‌جا شود.

| کاربر | رمز | مرکز | نقش |
|-------|-----|------|-----|
| admin | admin123 | default | platform admin |
| clinician | clinician123 | tehran-general | clinician |
| researcher | researcher123 | isfahan-medical | researcher |

```env
MULTI_TENANCY_ENABLED=true
DEFAULT_TENANT_ID=default
```

### API مدیریت مراکز

| Endpoint | نقش |
|----------|-----|
| `GET /api/v1/tenants` | لیست مراکز (platform admin) |
| `GET /api/v1/tenants/{tenant_id}` | جزئیات + تنظیمات |
| `PUT /api/v1/tenants/{tenant_id}/settings` | به‌روزرسانی برندینگ/UI |
| `GET /api/v1/tenants/{tenant_id}/quota` | وضعیت سهمیه |
| `GET /api/v1/tenants/{tenant_id}/billing` | برآورد هزینه ماهانه |
| `GET /api/v1/tenants/{tenant_id}/usage` | مصرف روزانه |

### داشبورد

صفحه **«مدیریت مراکز»** (platform admin): سوییچر tenant، quota، billing، تنظیمات برندینگ.

## گزارش‌های مدیریتی و اعلان‌ها

### گزارش هفتگی PDF/Excel

هر یکشنبه ساعت ۸ صبح (Celery Beat) گزارش هفتگی برای مدیران هر مرکز تولید و ایمیل می‌شود.

| Endpoint | نقش |
|----------|-----|
| `GET /api/v1/reports/weekly/summary` | خلاصه KPI هفته |
| `GET /api/v1/reports/weekly/export/excel` | دانلود Excel |
| `GET /api/v1/reports/weekly/export/pdf` | دانلود PDF |
| `POST /api/v1/reports/weekly/trigger` | ارسال فوری (admin) |
| `GET /api/v1/reports/weekly/archives` | آرشیو گزارش‌ها |

```bash
psql $DATABASE_URL -f docker/postgres/migrations/010_notifications_reports.sql
```

### ایمیل / پیامک هشدار critical

هشدارهای `critical` (و قابل تنظیم) به مدیران ارسال می‌شود:

- **Batch ML** → پس از `persist_alerts`
- **Streaming** → Faust / Redis → Celery `send_alert_notification`

```env
NOTIFICATIONS_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_USER=...
SMTP_PASSWORD=...
SMS_PROVIDER=kavenegar   # یا twilio
KAVENEGAR_API_KEY=...
ALERT_NOTIFY_MIN_SEVERITY=critical
```

| Endpoint | نقش |
|----------|-----|
| `GET /api/v1/reports/notifications/preferences` | لیست گیرندگان |
| `PUT /api/v1/reports/notifications/preferences` | افزودن/ویرایش |
| `GET /api/v1/reports/notifications/log` | لاگ ارسال |

### داشبورد موبایل (PWA)

اپلیکیشن وب قابل نصب روی iOS/Android:

- **آدرس:** `http://localhost:8000/mobile/`
- **Production:** `https://mobile.barekat.local/`
- KPI، هشدارهای فعال، WebSocket بلادرنگ، دانلود گزارش هفتگی
- Service Worker برای offline shell

داشبورد Streamlit → صفحه **«گزارش‌های مدیریتی»**

## Observability (Prometheus + Grafana + Loki)

پشته مانیتورینگ کامل برای production:

```
Services ──metrics──► Prometheus ──alert rules──► Alertmanager ──webhook──► API (email/SMS)
     │                      │
     └──logs──► Promtail ──► Loki ──────────────► Grafana Dashboards
```

### راه‌اندازی

```bash
make observability-up
```

| سرویس | آدرس | کاربرد |
|--------|------|--------|
| **Grafana** | http://localhost:3000 | داشبورد (admin / barekat_grafana) |
| **Prometheus** | http://localhost:9090 | متریک‌ها + alert rules |
| **Loki** | http://localhost:3100 | لاگ متمرکز |

### Alert Rules

| Alert | شرط | شدت |
|-------|------|-----|
| `ETLJobFailed` | ETL failed در ۱ ساعت | critical |
| `ETLStale` | بدون ETL موفق > ۲ ساعت | warning |
| `ModelDriftDetected` | PSI یا AUC drop | critical |
| `ModelAucDrop` | افت AUC > ۵٪ | warning |

```bash
psql $DATABASE_URL -f docker/postgres/migrations/012_observability.sql
```

## Data Lake (MinIO — Bronze / Silver / Gold)

برای Big Data واقعی، پلتفرم از معماری **Medallion** روی MinIO پشتیبانی می‌کند:

```
                    ┌─────────────────────────────────────────┐
  CSV / HL7 / FHIR  │  BRONZE (raw, immutable, partitioned)   │
  Kafka stream  ──► │  s3://health-lake/bronze/...            │
                    └──────────────┬──────────────────────────┘
                                   │ Spark batch / pandas
                    ┌──────────────▼──────────────────────────┐
                    │  SILVER (curated, typed, deduplicated)  │
                    │  Delta / Iceberg / Parquet              │
                    └──────────────┬──────────────────────────┘
                                   │ aggregations
                    ┌──────────────▼──────────────────────────┐
                    │  GOLD (marts: admission_summary, ...)   │
                    │  Delta / Iceberg                        │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  PostgreSQL analytics.* (serving layer) │
                    └─────────────────────────────────────────┘
```

### لایه‌ها

| لایه | مسیر MinIO | فرمت | محتوا |
|------|-----------|------|--------|
| **Bronze** | `bronze/csv/{table}/dt=...` | Parquet | داده خام CSV، HL7/FHIR archive |
| **Bronze** | `bronze/stream/events` | Delta | رویدادهای Kafka |
| **Silver** | `silver/health/{table}` | Delta/Iceberg | patients, admissions, ... |
| **Gold** | `gold/marts/{mart}` | Delta/Iceberg | admission_summary, department_stats |

### Versioning (Delta / Iceberg)

```env
LAKE_TABLE_FORMAT=delta      # یا iceberg
LAKE_SPARK_ENABLED=true      # Spark batch روی cluster
```

- **Delta Lake**: time-travel، ACID، `MERGE`/`OVERWRITE`
- **Iceberg**: Hadoop catalog روی MinIO (`spark.sql.catalog.lake`)
- متادیتا و نسخه جداول: `lake.table_registry` (PostgreSQL)

### Migration

```bash
psql $DATABASE_URL -f docker/postgres/migrations/011_data_lake.sql
```

### اجرا

```bash
make lake                    # pandas fallback (بدون Spark)
make lake-spark              # Spark + Delta روی MinIO
make etl                     # ETL + auto bronze landing

# Spark streaming → Delta bronze
spark-submit src/barekat/streaming/spark_streaming_job.py
```

### API

| Endpoint | نقش |
|----------|-----|
| `GET /api/v1/lake/status` | وضعیت lake + جداول + jobs |
| `GET /api/v1/lake/tables` | لیست جداول per-layer |
| `POST /api/v1/lake/run/full` | pipeline کامل (Celery) |
| `POST /api/v1/lake/run/silver` | bronze → silver |
| `POST /api/v1/lake/run/gold` | silver → gold |

Celery Beat: `lake-batch-weekly` — دوشنبه ساعت ۱ صبح.

### وابستگی‌های Spark (اختیاری)

```bash
pip install -r requirements-spark.txt
```

## هم‌کاری FHIR R4 (استاندارد مدرن)

علاوه بر HL7 v2، پلتفرم از **FHIR R4** با منابع اصلی پشتیبانی می‌کند:

| Resource | کاربرد |
|----------|--------|
| **Patient** | شناسه ملی، نام فارسی/انگلیسی، demographics |
| **Encounter** | بستری، بخش، نوع پذیرش |
| **Observation** | علائم حیاتی، نتایج آزمایش (LOINC) |
| **Condition** | تشخیص ICD-10، وضعیت بالینی |

### پروفایل‌های سیستم بیمارستانی

| پروفایل | منطقه | سیستم |
|---------|--------|--------|
| `iran_moh` | ایران | وزارت بهداشت / SEPAS |
| `iran_salamat` | ایران | بیمه سلامت |
| `iran_tamin` | ایران | تأمین اجتماعی |
| `international_us_core` | بین‌الملل | US Core R4 |
| `international_ips` | بین‌الملل | International Patient Summary |
| `international_epic` | بین‌الملل | Epic on FHIR |
| `international_hapi` | بین‌الملل | HAPI FHIR (تست) |

### API هم‌کاری

```bash
# قابلیت‌ها و پروفایل‌ها
GET /api/v1/fhir/capabilities
GET /api/v1/fhir/profiles?region=IR

# دریافت Bundle FHIR (Patient + Encounter + Observation + Condition)
POST /api/v1/fhir/bundle
{"bundle": {...}, "profile": "iran_salamat", "persist": true, "stream": true}

# تست اتصال به سیستم بیمارستانی
POST /api/v1/fhir/connectors/test
{"profile": "international_hapi", "base_url": "https://hapi.fhir.org/baseR4"}

# همگام‌سازی از سیستم خارجی (با کد ملی)
POST /api/v1/fhir/connectors/sync
{"profile": "iran_salamat", "national_id": "0012345678", "persist": true}
```

### جریان داده

```
سیستم بیمارستانی (SEPAS / Epic / HAPI)
        ↓ FHIR REST
   HospitalFHIRConnector
        ↓ parse + normalize
   raw.patients / admissions / diagnoses / lab_results
        ↓
   Kafka → Faust → هشدار WebSocket
```

## پردازش جریانی بلادرنگ (Kafka + Faust)

زیرساخت Kafka از قبل وجود داشت؛ اکنون ingest، پردازش و هشدار WebSocket فعال است.

```
HL7/FHIR → API Ingest → Kafka (health.events.raw)
                              ↓
                        Faust Worker
                              ↓
              health.alerts + Redis pub/sub + PostgreSQL
                              ↓
                    WebSocket → Dashboard
```

### Ingest بلادرنگ

| Endpoint | توضیح |
|----------|--------|
| `POST /api/v1/ingest/hl7` | پیام HL7 v2.x (JSON: `{"message": "MSH|..."}`) |
| `POST /api/v1/ingest/hl7/raw` | body خام text/plain |
| `POST /api/v1/ingest/fhir` | منبع FHIR JSON (Patient, Encounter, Observation) |

### پردازش جریانی

- **Faust** (پیش‌فرض): `make faust` یا سرویس Docker `faust-worker`
- **Spark Streaming** (اختیاری): `src/barekat/streaming/spark_streaming_job.py` — نیاز به `pyspark`

Faust رویدادها را نرمال‌سازی می‌کند، قوانین vitals را ارزیابی می‌کند و هشدار تولید می‌کند.

### هشدار بلادرنگ در داشبورد

- WebSocket: `ws://localhost:8000/api/v1/stream/alerts`
- REST fallback: `GET /api/v1/stream/alerts/recent`
- صفحه **هشدارها** در داشبورد — پنل WebSocket زنده

### شبیه‌سازی

```bash
# 1. زیرساخت
make infra
make up   # شامل faust-worker

# 2. دریافت JWT
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 3. ارسال رویدادهای نمونه
python scripts/simulate_stream.py --token <JWT> --count 20 --interval 0.5
```

### Kafka Topics

| Topic | نقش |
|-------|-----|
| `health.events.raw` | رویدادهای نرمال‌شده HL7/FHIR |
| `health.hl7` | کپی رویدادهای HL7 |
| `health.fhir` | کپی رویدادهای FHIR |
| `health.alerts` | هشدارهای تولیدشده |

### اجرا (فقط CSV)

```bash
# اگر PostgreSQL در دسترس نیست
set DASHBOARD_DATA_SOURCE=csv
streamlit run dashboards/app.py
```

## CI/CD و محیط‌ها

[![CI](https://github.com/parsasohrab1/BAREKAT-Big-Data-Analytics-in-Health/actions/workflows/ci.yml/badge.svg)](https://github.com/parsasohrab1/BAREKAT-Big-Data-Analytics-in-Health/actions/workflows/ci.yml)

### GitHub Actions

فایل `.github/workflows/ci.yml` چهار job اجرا می‌کند:

| Job | محتوا |
|-----|--------|
| **lint** | `ruff check` |
| **unit-test** | تست‌های واحد (بدون PostgreSQL) |
| **integration-test** | تست یکپارچگی ETL و API با سرویس PostgreSQL |
| **docker-build** | ساخت imageهای API، Dashboard و Worker |

### تست‌ها

```bash
# تست واحد (پیش‌فرض — integration skip می‌شود)
make test

# تست یکپارچگی (نیاز به PostgreSQL)
export POSTGRES_DB=barekat_health_test
python scripts/apply_init_sql.py
make test-integration

# lint
make lint
```

تست‌های یکپارچگی در `tests/integration/`:

- **ETL**: بارگذاری CSV نمونه → `ETLPipeline` → بررسی `raw.*` و `audit.etl_runs`
- **API**: `/health`، login JWT، `/api/v1/analytics/summary`، `/api/v1/analytics/etl/runs`

### محیط Staging (جدا از Production)

پورت‌ها و volumeهای جدا — بدون تداخل با development:

| سرویس | Development | Staging |
|--------|-------------|---------|
| PostgreSQL | 5432 | **5433** |
| API | 8000 | **8001** |
| Dashboard | 8501 | **8502** |
| Redis | 6379 | **6380** |

```bash
cp .env.staging.example .env.staging
# ویرایش رمزها
make staging-up
```

### محیط Production

```bash
cp .env.production.example .env.production
# تنظیم JWT_SECRET و رمزهای قوی
make prod-up
```

تفاوت‌های کلیدی production:

- `BAREKAT_ENV=production`
- بدون bind mount سورس کد
- `restart: unless-stopped`
- PostgreSQL فقط در شبکه داخلی Docker (بدون expose عمومی)
