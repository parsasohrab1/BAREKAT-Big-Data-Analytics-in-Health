# BAREKAT - Big Data Analytics in Health

A health big data analytics platform for processing and analyzing EHR data, laboratory data, medical images (DICOM) and real-time clinical events (HL7/FHIR).

> **Roadmap:** Genomic data and wearable devices are not implemented in the current version.

## Infrastructure Architecture

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

### Services

| Service | Port | Role |
|--------|------|-----|
| PostgreSQL | 5432 | Data Warehouse |
| MinIO | 9000/9001 | File storage (DICOM, HL7, CSV) |
| Redis | 6379 | Cache and session |
| Kafka | 9092 | Streaming event processing |
| Spark | 7077/8080 | Distributed processing |
| API | 8000 | REST API with RBAC |
| Dashboard | 8501 | Analytics dashboard |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Make (optional)

### Installation

```bash
# 1. Clone and install dependencies
cp .env.example .env
pip install -r requirements.txt
pip install -e .

# 2. Start the Docker infrastructure
docker compose up -d postgres minio redis

# 3. Generate synthetic data
python scripts/generate_data.py --patients 1000 --admissions 3000

# 4. Run ETL (incremental - default)
python -m barekat.etl.pipeline --mode incremental

# Or full load
python -m barekat.etl.pipeline --mode full

# 5. Train the ML models
python -m barekat.ml.pipeline

# 6. Start the API
uvicorn barekat.api.main:app --reload --port 8000

# 7. Dashboard
streamlit run dashboards/app.py
```

### With the Makefile

```bash
make setup          # install dependencies
make infra          # Docker services
make generate-data  # generate data
make etl            # ETL incremental
make etl-full       # ETL full reload
make worker         # Celery worker
make beat           # Celery Beat scheduler
make train          # ML training
make api            # API server
make dashboard      # dashboard
make test           # tests
```

## Project Structure

```
├── docker/              # Docker settings
│   ├── postgres/        # Database schema
│   ├── api/             # Dockerfile API
│   └── dashboard/       # Dashboard Dockerfile
├── src/barekat/         # main code
│   ├── api/             # FastAPI endpoints
│   ├── config/          # settings
│   ├── etl/             # ETL pipeline + validation + incremental
│   ├── worker/          # Celery Beat scheduling
│   ├── ingestion/       # CSV/HL7/DICOM loading
│   ├── ml/              # ML models
│   ├── security/        # authentication and RBAC
│   └── storage/         # PostgreSQL, MinIO, Redis, Kafka
├── scripts/             # helper scripts
├── dashboards/          # professional Streamlit dashboard
│   ├── app.py           # dashboard entry point
│   ├── pages/           # analytics pages
│   └── utils/           # data loading, charts, ML
├── data/                # raw and processed data
└── tests/               # tests
```

## API

API documentation: `http://localhost:8000/docs`

### Authentication

Login is done from the `audit.users` table with bcrypt. In production, `AUTH_DEV_FALLBACK=false` should be set.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

### Automatic Migration

The migrations `docker/postgres/migrations/002` through `013` are applied automatically at API startup (`DB_AUTO_MIGRATE=true`) or with the following command:

```bash
make db-migrate
# or
python scripts/apply_init_sql.py   # init.sql + all migrations (CI/test)
```

### User Roles (RBAC)

| Role | Permissions |
|-----|-----------|
| admin | Full management, ETL, users |
| clinician | View PHI, alerts |
| researcher | Analytics, export |
| viewer | Read-only |

## Security and Privacy

- JWT authentication
- Role-based access control (RBAC)
- Access log in the `audit` schema
- Communication encryption (TLS in production)

## Synthetic Data Generation

Main script: `scripts/generate_data.py` (previous version: `scripts/original_DATA.py`)

Tables: Patients, Admissions, Diagnoses, Medications, Lab_Results

## Advanced ETL

### Automatic Scheduling (Celery Beat)

```bash
# Docker
docker compose up -d celery-worker celery-beat

# Local
make worker   # terminal 1
make beat     # terminal 2
```

| Job | Schedule | Mode |
|-----|----------|------|
| `etl-incremental-hourly` | Every hour | incremental |
| `etl-full-daily` | Daily at 2 AM | full reload |

### Schema Validation (Great Expectations)

Before loading, each table is validated with Great Expectations (null checks, age range, PK uniqueness). On failure, the ETL stops and is recorded in `audit.etl_runs`.

```bash
python -m barekat.etl.pipeline --mode incremental
python -m barekat.etl.pipeline --mode full --skip-validation  # development only
```

### Incremental Loading

- New records: `INSERT`
- Existing records: `UPSERT` (ON CONFLICT)
- watermark in `staging.etl_watermarks`
- `full` mode: `TRUNCATE` + reload

### Execution Log and Retry

Each run is recorded in `audit.etl_runs`:

```bash
# API
GET /api/v1/analytics/etl/runs

# Dashboard → Infrastructure page
```

On error, Celery retries up to 3 times (configurable).

## MLOps

### Model Versioning and Metrics

Each training run is recorded in `analytics.ml_model_registry`:

- Version (`v20260713_003000`)
- artifact in `data/models/{model_name}/{version}/`
- Metrics: AUC, F1, precision, recall, Brier score
- calibration data (reliability diagram)

```bash
python -m barekat.ml.pipeline
python -m barekat.ml.pipeline --retrain   # new data from PostgreSQL
```

### Advanced Models

| Model | Use | API |
|-----|--------|-----|
| **LOS** | Bed planning | `GET /api/v1/ml/predict/los` |
| **Mortality / Sepsis** | Early warning | `GET /api/v1/ml/predict/early-warning` |
| **Physician note NLP** | ICD diagnosis extraction | `POST /api/v1/ml/nlp/extract-diagnoses` |
| **Vital signs (time-series)** | Real-time monitoring | `GET /api/v1/ml/vitals/monitor/{admission_id}` |

New data: `clinical_notes.csv`, `vital_signs.csv` + the fields `Mortality_Flag`, `Sepsis_Flag` in admissions.

```bash
python scripts/generate_data.py --patients 1000 --admissions 3000
python -m barekat.ml.pipeline   # train all models + generate alerts
```

### Model API

| Endpoint | Role |
|----------|-----|
| `POST /api/v1/ml/train` | Training |
| `POST /api/v1/ml/retrain` | Retrain with new data |
| `GET /api/v1/ml/models` | List versions |
| `GET /api/v1/ml/models/readmission/metrics` | Metrics and calibration |
| `GET /api/v1/ml/predict/readmission/explain/{admission_id}` | SHAP explanation — why high risk? |
| `GET /api/v1/ml/predict/readmission/report/{admission_id}` | Printable HTML report |
| `GET /api/v1/ml/thresholds` | Per-department thresholds |
| `PUT /api/v1/ml/thresholds/{department}` | Set a threshold |

### Per-Department Risk Threshold

The table `analytics.department_risk_thresholds` — each department has its own threshold (e.g., Cardiology: 0.75, Pediatrics: 0.65).

### Periodic Retrain

Celery Beat job `ml-retrain-weekly` — every Monday at 3 AM (configurable):

```env
ML_RETRAIN_DAY_OF_WEEK=0
ML_RETRAIN_HOUR=3
```

## Analytics Dashboard

The professional Streamlit dashboard in `dashboards/app.py` shows all platform capabilities.

**Address:** `http://localhost:8501`

### Dashboard Pages

| Page | Content |
|------|--------|
| Overview | KPIs, gauges, admission trend, recent admissions table |
| Patient Population | Age, BMI, diabetes, hypertension, smoking, blood type |
| Admissions and Departments | Department distribution, LOS, ICU, admission type |
| Diagnoses | ICD-10, primary/secondary diagnosis, diagnosis-department map |
| Medications | Most-prescribed drugs, frequency of use, medication map |
| Laboratory | Abnormal results, test distribution, histogram |
| ML Analytics | Readmission prediction, clustering, feature importance |
| Alerts | Risk alerts with severity levels and CSV download |
| Center Management | Tenant switch, quota, billing, branding settings (platform admin) |
| Management Reports | Weekly PDF/Excel report, email/SMS settings |
| Infrastructure | Data status, architecture, data quality, capabilities |

### Global Filters

From the sidebar you can filter by **department**, **gender** and **admission type**.

### Dashboard Authentication

The dashboard is protected with JWT and RBAC. After login, pages are displayed based on role.

| User | Password | Role | Center |
|-------|-----|-----|------|
| admin | admin123 | Full access (platform admin) | default |
| clinician | clinician123 | PHI + alert approval | tehran-general |
| researcher | researcher123 | Analytics and ML | isfahan-medical |

### Data Source

After ETL, the dashboard reads automatically from **PostgreSQL** (`DASHBOARD_DATA_SOURCE=auto`).

```bash
# 1. Generate data
python scripts/generate_data.py --patients 1000 --admissions 3000

# 2. ETL to PostgreSQL
python -m barekat.etl.pipeline

# 3. ML + store alerts in analytics.predictive_alerts
python -m barekat.ml.pipeline

# 4. Run the dashboard
streamlit run dashboards/app.py
```

### Real Alerts

Alerts are stored in the `analytics.predictive_alerts` table after `python -m barekat.ml.pipeline` and are displayed on the **Alerts** page. The `clinician` and `admin` roles can approve an alert.

streamlit run dashboards/app.py
```

## Medical Images (DICOM / PACS)

In addition to metadata, PACS connection, thumbnails and the viewer are now active.

```
PACS (C-ECHO/C-FIND or Orthanc REST)
        ↓ retrieve
   MinIO (dicom/*.dcm + thumbnails)
        ↓
   raw.dicom_studies + Dashboard Viewer
        ↓ (next phase)
   CAD — computer-aided diagnosis
```

### API (`/api/v1/imaging`)

| Endpoint | Use |
|----------|--------|
| `POST /pacs/echo` | Test PACS connection (C-ECHO) |
| `POST /pacs/query` | Search studies (C-FIND / Orthanc) |
| `POST /pacs/retrieve` | Retrieve a study from PACS → MinIO |
| `POST /upload` | Upload a `.dcm` file |
| `GET /studies` | Studies catalog |
| `GET /studies/{uid}/thumbnail` | PNG thumbnail |
| `GET /studies/{uid}/viewer?window=&level=` | Viewer image with Window/Level |
| `GET /studies/{uid}/cad` | CAD stub (next phase) |

### Setup

```bash
# Generate sample DICOM
python scripts/generate_sample_dicom.py --output ./data/dicom --count 5

# ingest into MinIO + PostgreSQL
python -c "from pathlib import Path; from barekat.imaging.store import ingest_directory; ingest_directory(Path('./data/dicom'))"

# Dashboard → "Medical Imaging" page
streamlit run dashboards/app.py
```

### PACS Settings (`.env`)

```env
PACS_HOST=localhost
PACS_PORT=4242
PACS_AE_TITLE=ORTHANC
PACS_ORTHANC_URL=http://localhost:8042
```

### CAD — Next Phase

Planned models: Chest X-ray (pneumothorax), CT (hemorrhage/PE), Mammography (mass).
For now `CADAnalyzer` returns only a stub — for research and development, not clinical use.

## Compliance and Privacy (HIPAA / GDPR / Domestic Regulations)

```
API / dashboard request
        ↓ AuditMiddleware
   audit.access_logs (who, when, which data)
        ↓
   RBAC + view_phi (minimum necessary)
        ↓
   Retention Celery Beat → automatic deletion of expired data
```

### Supported Frameworks

| Framework | Coverage |
|--------|------|
| **HIPAA** | RBAC, audit trail, minimum necessary, de-identification |
| **GDPR** | Consent, right to erasure, pseudonymization, retention |
| **Domestic regulations** | SEPAS, national ID (not stored in analytics), Ministry of Health resolutions |

### API (`/api/v1/compliance`)

| Endpoint | Use |
|----------|--------|
| `GET /frameworks` | Active legal frameworks |
| `GET /summary` | Compliance coverage summary (admin) |
| `GET /audit-logs` | Full access log |
| `POST /pseudonymize/{id}` | Re-pseudonymization (reversible) |
| `POST /anonymize/{id}` | Anonymization (irreversible) |
| `POST /erasure/{id}` | GDPR right to erasure |
| `GET /retention/policies` | Retention policy |
| `POST /retention/purge` | Manual deletion of expired data |
| `POST /consent` | Record a consent form |
| `POST /legal-hold` | Legal hold (stop deletion) |
| `GET /export/deidentified` | De-ID research export |

### Default Retention Policy

| Data category | Duration | Reference |
|-----------|-----|------|
| Clinical notes | 7 years | HIPAA/GDPR/IR-MOH |
| Lab results | 5 years | HIPAA |
| DICOM images | 10 years | IR-MOH |
| Access log | 6 years | HIPAA/GDPR |

### Settings (`.env`)

```env
AUDIT_ENABLED=true
AUDIT_LOG_IP=true
COMPLIANCE_FRAMEWORK=all
PSEUDONYMIZATION_SALT=change-me-pseudonym-salt
DATA_RETENTION_ENABLED=true
RETENTION_PURGE_HOUR=4
REQUIRE_CONSENT_FOR_RESEARCH=false
```

Dashboard → **"Compliance and Privacy"** page (admin only).

## Infrastructure Security (TLS / Secrets / MFA / WAF)

```
Client ──TLS──► Nginx (WAF + rate limit)
                    ├── api.barekat.local      → API
                    ├── dashboard.barekat.local → Streamlit
                    └── minio.barekat.local    → MinIO (SSE)

Secrets: Docker Secrets (/run/secrets/*) or HashiCorp Vault
PHI at-rest: Fernet encryption (clinical_notes) + MinIO KMS
Admin MFA: TOTP (Google Authenticator / Authy)
```

### Secure Stack Setup

```bash
make secrets      # generate secret files in ./secrets/
make tls-certs    # self-signed TLS certificate
make secure-up    # prod + docker-compose.secure.yml
```

### Docker Secrets (alternative to .env)

| Secret | Path |
|--------|------|
| `jwt_secret` | `/run/secrets/jwt_secret` |
| `postgres_password` | `/run/secrets/postgres_password` |
| `phi_encryption_key` | `/run/secrets/phi_encryption_key` |
| `minio_secret_key` | `/run/secrets/minio_secret_key` |

Vault (optional): `VAULT_ADDR` + `VAULT_TOKEN` → KV path `barekat`

### MFA for Admin

```bash
# 1. Login as admin
# 2. POST /api/v1/auth/mfa/enroll  → QR code
# 3. POST /api/v1/auth/mfa/activate {"code": "123456"}
# 4. Login → mfa_token → POST /api/v1/auth/mfa/verify
```

### Rate Limiting & WAF

| Layer | Protection |
|------|--------|
| **Nginx** | `limit_req`, bad-bot block, SQLi/XSS in the query string |
| **FastAPI** | Redis rate limit (120/min API, 10/min login) |
| **SecurityMiddleware** | WAF patterns, HSTS, CSP, X-Frame-Options |

### PHI At-Rest Encryption

```bash
# Enable
PHI_ENCRYPTION_ENABLED=true
PHI_ENCRYPTION_KEY_FILE=/run/secrets/phi_encryption_key

# Encrypt existing notes
POST /api/v1/compliance/phi/encrypt
```

## Multi-Tenancy

The platform supports multiple hospitals/medical centers simultaneously:

| Capability | Description |
|--------|--------|
| **Data isolation** | `tenant_id` column on `raw.*` and `analytics.*` tables + automatic filtering in the API and dashboard |
| **Dedicated settings** | Logo, primary color, locale, timezone, active pages per-tenant |
| **Dedicated dashboard** | Sidebar branding and per-tenant data cache |
| **Billing & Quota** | Plan (starter/pro/enterprise), patient/API/storage limits, daily metering |

### Schema

```
tenant.tenants          — centers (slug, plan, status)
tenant.plans            — starter / pro / enterprise
tenant.tenant_settings  — branding and UI settings
tenant.tenant_users     — user → tenant mapping
tenant.usage_records    — API usage (metering)
tenant.usage_summary    — daily summary
```

### Migration

```bash
# After PostgreSQL setup
psql $DATABASE_URL -f docker/postgres/migrations/009_multi_tenancy.sql
```

Sample centers: `default`, `tehran-general`, `isfahan-medical`, `mashhad-university`

### Authentication and Context

The JWT includes `tenant_id` and `tenant_slug`. A platform admin can switch between centers with the `X-Tenant-ID` header.

| User | Password | Center | Role |
|-------|-----|------|-----|
| admin | admin123 | default | platform admin |
| clinician | clinician123 | tehran-general | clinician |
| researcher | researcher123 | isfahan-medical | researcher |

```env
MULTI_TENANCY_ENABLED=true
DEFAULT_TENANT_ID=default
```

### Center Management API

| Endpoint | Role |
|----------|-----|
| `GET /api/v1/tenants` | List centers (platform admin) |
| `GET /api/v1/tenants/{tenant_id}` | Details + settings |
| `PUT /api/v1/tenants/{tenant_id}/settings` | Update branding/UI |
| `GET /api/v1/tenants/{tenant_id}/quota` | Quota status |
| `GET /api/v1/tenants/{tenant_id}/billing` | Monthly cost estimate |
| `GET /api/v1/tenants/{tenant_id}/usage` | Daily usage |

### Dashboard

The **"Center Management"** page (platform admin): tenant switcher, quota, billing, branding settings.

## Management Reports and Notifications

### Weekly PDF/Excel Report

Every Sunday at 8 AM (Celery Beat) a weekly report is generated and emailed to the managers of each center.

| Endpoint | Role |
|----------|-----|
| `GET /api/v1/reports/weekly/summary` | Weekly KPI summary |
| `GET /api/v1/reports/weekly/export/excel` | Download Excel |
| `GET /api/v1/reports/weekly/export/pdf` | Download PDF |
| `POST /api/v1/reports/weekly/trigger` | Immediate send (admin) |
| `GET /api/v1/reports/weekly/archives` | Report archive |

```bash
psql $DATABASE_URL -f docker/postgres/migrations/010_notifications_reports.sql
```

### Critical Alert Email / SMS

`critical` alerts (and configurable) are sent to managers:

- **Batch ML** → after `persist_alerts`
- **Streaming** → Faust / Redis → Celery `send_alert_notification`

```env
NOTIFICATIONS_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_USER=...
SMTP_PASSWORD=...
SMS_PROVIDER=kavenegar   # or twilio
KAVENEGAR_API_KEY=...
ALERT_NOTIFY_MIN_SEVERITY=critical
```

| Endpoint | Role |
|----------|-----|
| `GET /api/v1/reports/notifications/preferences` | List recipients |
| `PUT /api/v1/reports/notifications/preferences` | Add/edit |
| `GET /api/v1/reports/notifications/log` | Delivery log |

### Mobile Dashboard (PWA)

Web app installable on iOS/Android:

- **Address:** `http://localhost:8000/mobile/`
- **Production:** `https://mobile.barekat.local/`
- KPI, active alerts, real-time WebSocket, weekly report download
- Service Worker for the offline shell

Streamlit dashboard → **"Management Reports"** page

## Observability (Prometheus + Grafana + Loki)

A full monitoring stack for production:

```
Services ──metrics──► Prometheus ──alert rules──► Alertmanager ──webhook──► API (email/SMS)
     │                      │
     └──logs──► Promtail ──► Loki ──────────────► Grafana Dashboards
```

### Setup

```bash
make observability-up
```

| Service | Address | Use |
|--------|------|--------|
| **Grafana** | http://localhost:3000 | Dashboard (admin / barekat_grafana) |
| **Prometheus** | http://localhost:9090 | Metrics + alert rules |
| **Loki** | http://localhost:3100 | Centralized logs |

### Alert Rules

| Alert | Condition | Severity |
|-------|------|-----|
| `ETLJobFailed` | ETL failed within 1 hour | critical |
| `ETLStale` | No successful ETL for > 2 hours | warning |
| `ModelDriftDetected` | PSI or AUC drop | critical |
| `ModelAucDrop` | AUC drop > 5% | warning |

```bash
psql $DATABASE_URL -f docker/postgres/migrations/012_observability.sql
```

## Data Lake (MinIO — Bronze / Silver / Gold)

For real Big Data, the platform supports a **Medallion** architecture on MinIO:

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

### Layers

| Layer | MinIO path | Format | Content |
|------|-----------|------|--------|
| **Bronze** | `bronze/csv/{table}/dt=...` | Parquet | Raw CSV data, HL7/FHIR archive |
| **Bronze** | `bronze/stream/events` | Delta | Kafka events |
| **Silver** | `silver/health/{table}` | Delta/Iceberg | patients, admissions, ... |
| **Gold** | `gold/marts/{mart}` | Delta/Iceberg | admission_summary, department_stats |

### Versioning (Delta / Iceberg)

```env
LAKE_TABLE_FORMAT=delta      # or iceberg
LAKE_SPARK_ENABLED=true      # Spark batch on a cluster
```

- **Delta Lake**: time-travel, ACID, `MERGE`/`OVERWRITE`
- **Iceberg**: Hadoop catalog on MinIO (`spark.sql.catalog.lake`)
- Table metadata and versions: `lake.table_registry` (PostgreSQL)

### Migration

```bash
psql $DATABASE_URL -f docker/postgres/migrations/011_data_lake.sql
```

### Running

```bash
make lake                    # pandas fallback (no Spark)
make lake-spark              # Spark + Delta on MinIO
make etl                     # ETL + auto bronze landing

# Spark streaming → Delta bronze
spark-submit src/barekat/streaming/spark_streaming_job.py
```

### API

| Endpoint | Role |
|----------|-----|
| `GET /api/v1/lake/status` | Lake status + tables + jobs |
| `GET /api/v1/lake/tables` | List tables per-layer |
| `POST /api/v1/lake/run/full` | Full pipeline (Celery) |
| `POST /api/v1/lake/run/silver` | bronze → silver |
| `POST /api/v1/lake/run/gold` | silver → gold |

Celery Beat: `lake-batch-weekly` — Monday at 1 AM.

### Spark Dependencies (optional)

```bash
pip install -r requirements-spark.txt
```

## FHIR R4 Interoperability (Modern Standard)

In addition to HL7 v2, the platform supports **FHIR R4** with the main resources:

| Resource | Use |
|----------|--------|
| **Patient** | National ID, Persian/English name, demographics |
| **Encounter** | Admission, department, admission type |
| **Observation** | Vital signs, lab results (LOINC) |
| **Condition** | ICD-10 diagnosis, clinical status |

### Hospital System Profiles

| Profile | Region | System |
|---------|--------|--------|
| `iran_moh` | Iran | Ministry of Health / SEPAS |
| `iran_salamat` | Iran | Salamat Insurance |
| `iran_tamin` | Iran | Social Security |
| `international_us_core` | International | US Core R4 |
| `international_ips` | International | International Patient Summary |
| `international_epic` | International | Epic on FHIR |
| `international_hapi` | International | HAPI FHIR (test) |

### Interoperability API

```bash
# Capabilities and profiles
GET /api/v1/fhir/capabilities
GET /api/v1/fhir/profiles?region=IR

# Get a FHIR Bundle (Patient + Encounter + Observation + Condition)
POST /api/v1/fhir/bundle
{"bundle": {...}, "profile": "iran_salamat", "persist": true, "stream": true}

# Test connection to the hospital system
POST /api/v1/fhir/connectors/test
{"profile": "international_hapi", "base_url": "https://hapi.fhir.org/baseR4"}

# Sync from the external system (with national ID)
POST /api/v1/fhir/connectors/sync
{"profile": "iran_salamat", "national_id": "0012345678", "persist": true}
```

### Data Flow

```
Hospital system (SEPAS / Epic / HAPI)
        ↓ FHIR REST
   HospitalFHIRConnector
        ↓ parse + normalize
   raw.patients / admissions / diagnoses / lab_results
        ↓
   Kafka → Faust → WebSocket alert
```

## Real-Time Stream Processing (Kafka + Faust)

The Kafka infrastructure already existed; ingestion, processing and WebSocket alerts are now active.

```
HL7/FHIR → API Ingest → Kafka (health.events.raw)
                              ↓
                        Faust Worker
                              ↓
              health.alerts + Redis pub/sub + PostgreSQL
                              ↓
                    WebSocket → Dashboard
```

### Real-Time Ingest

| Endpoint | Description |
|----------|--------|
| `POST /api/v1/ingest/hl7` | HL7 v2.x message (JSON: `{"message": "MSH|..."}`) |
| `POST /api/v1/ingest/hl7/raw` | Raw text/plain body |
| `POST /api/v1/ingest/fhir` | FHIR JSON resource (Patient, Encounter, Observation) |

### Stream Processing

- **Faust** (default): `make faust` or the Docker service `faust-worker`
- **Spark Streaming** (optional): `src/barekat/streaming/spark_streaming_job.py` — requires `pyspark`

Faust normalizes events, evaluates vitals rules and generates alerts.

### Real-Time Alerts on the Dashboard

- WebSocket: `ws://localhost:8000/api/v1/stream/alerts`
- REST fallback: `GET /api/v1/stream/alerts/recent`
- **Alerts** page on the dashboard — live WebSocket panel

### Simulation

```bash
# 1. Infrastructure
make infra
make up   # includes faust-worker

# 2. Get a JWT
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 3. Send sample events
python scripts/simulate_stream.py --token <JWT> --count 20 --interval 0.5
```

### Kafka Topics

| Topic | Role |
|-------|-----|
| `health.events.raw` | Normalized HL7/FHIR events |
| `health.hl7` | Copy of HL7 events |
| `health.fhir` | Copy of FHIR events |
| `health.alerts` | Generated alerts |

### Execution (CSV only)

```bash
# If PostgreSQL is not available
set DASHBOARD_DATA_SOURCE=csv
streamlit run dashboards/app.py
```

## CI/CD and Environments

[![CI](https://github.com/parsasohrab1/BAREKAT-Big-Data-Analytics-in-Health/actions/workflows/ci.yml/badge.svg)](https://github.com/parsasohrab1/BAREKAT-Big-Data-Analytics-in-Health/actions/workflows/ci.yml)

### GitHub Actions

The file `.github/workflows/ci.yml` runs four jobs:

| Job | Content |
|-----|--------|
| **lint** | `ruff check` |
| **unit-test** | Unit tests (without PostgreSQL) |
| **integration-test** | ETL and API integration tests with a PostgreSQL service |
| **docker-build** | Build the API, Dashboard and Worker images |

### Tests

```bash
# Unit test (default — integration is skipped)
make test

# Integration test (requires PostgreSQL)
export POSTGRES_DB=barekat_health_test
python scripts/apply_init_sql.py
make test-integration

# lint
make lint
```

Integration tests are in `tests/integration/`:

- **ETL**: load sample CSV → `ETLPipeline` → check `raw.*` and `audit.etl_runs`
- **API**: `/health`, JWT login, `/api/v1/analytics/summary`, `/api/v1/analytics/etl/runs`

### Staging Environment (separate from Production)

Separate ports and volumes — no conflict with development:

| Service | Development | Staging |
|--------|-------------|---------|
| PostgreSQL | 5432 | **5433** |
| API | 8000 | **8001** |
| Dashboard | 8501 | **8502** |
| Redis | 6379 | **6380** |

```bash
cp .env.staging.example .env.staging
# Edit the passwords
make staging-up
```

### Production Environment

```bash
cp .env.production.example .env.production
# Set JWT_SECRET and strong passwords
make prod-up
```

Key production differences:

- `BAREKAT_ENV=production`
- No source code bind mount
- `restart: unless-stopped`
- PostgreSQL only on the internal Docker network (no public exposure)
