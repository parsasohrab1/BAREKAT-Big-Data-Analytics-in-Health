# BAREKAT — TRL 5 Validation Plan and Evidence

**Goal:** advance BAREKAT from TRL 4 (components validated in lab) to **TRL 5** (integrated technology validated in a *relevant environment*).

## 1. TRL 5 definition used here

> Basic technological components are integrated and tested together with realistic supporting elements, in an environment that simulates the intended one closely enough to be meaningful.

For BAREKAT the intended environment is a hospital deployment: PostgreSQL warehouse, Kafka event stream, MinIO lake, Redis, API with JWT/RBAC and audit, ML models, fed by clinical-shaped data at realistic volume.

## 2. Starting point (TRL 4 evidence already in the repo)

- 65 unit tests pass (one SHAP test fails locally due to an OpenCV/NumPy ABI mismatch, so it needs a pinned, clean environment).
- Integration tests exist for API, auth, ETL, Kafka, MinIO but are excluded by default (`-m 'not integration'`) and were never run as one system.
- No documented acceptance criteria, no load/latency data, no validation at volume.

## 3. Acceptance criteria (declared before the run)

| # | Criterion | Gate |
|---|---|---|
| S1 | PostgreSQL, Redis, MinIO, Kafka reachable | all up |
| S2 | Schema + migrations idempotent | two applications, no error |
| S3 | ETL 5,000 patients / 15,000 admissions, validation ON | row counts equal input; 0 orphans; ≥500 rows/s; re-run adds no duplicates |
| S4 | Medallion lake on MinIO | pipeline success, tables catalogued |
| S5 | ML training + registry | models registered; readmission AUC ≥ 0.60 |
| S6 | Live API | unauthenticated rejected; bad login 401; RBAC 403; summary equals DB; 200 requests @ concurrency 10, all 200, p95 ≤ 500 ms |
| S7 | Streaming | HL7 POST appears on Kafka ≤ 15 s; malformed HL7 → 400 |
| S8 | Compliance/observability | audit rows written by API traffic; `/metrics` served |
| S9 | Full test suite incl. integration | 0 failures |

Run: `make validate-trl5` → writes `docs/trl5/validation_report.{md,json}`.

## 4. Results

Environment: single-node Docker Desktop (Windows) for PostgreSQL 16, Redis 7, MinIO, Kafka 7.6; API and harness on the host (Python 3.10). Dataset: 5,000 patients / 15,000 admissions (~470k rows including vitals and notes).

| Stage | Outcome | Evidence |
|---|---|---|
| S1 infrastructure | PASS | all four services reachable |
| S2 migrations | PASS | applied twice without error |
| S3 ETL at scale | PASS | counts equal input, 0 orphans, idempotent re-run, 2,830 rows/s (gate 500) |
| S4 data lake | PASS | bronze/silver/gold, 16 tables catalogued |
| S5 ML | PASS | readmission test AUC 0.71 (gate 0.60); 6 model families trained and registered |
| S6 API | PASS at full scale on an idle host (p95 295 ms, 200/200 OK, login throttled after 7 attempts); **not re-confirmed after the final code changes** | later runs were taken while unrelated processes held the host CPU at 100% (even `/health` took 550 ms), so those numbers are not valid measurements |
| S7 streaming | PASS | HL7 POST visible on Kafka in 3.3 s; malformed HL7 rejected with 400 |
| S8 audit/metrics | PASS | audit rows written by API traffic; `/metrics` served |
| S9 test suite | PASS | 80 passed (unit + integration) on the final merged code |

**Known limitations of this evidence**

- **Great Expectations schema validation was not exercised** (package not installable on the test host). The harness records this as `SKIPPED` rather than passing it silently.
- **S6 must be re-run on a quiet machine** (`make validate-trl5` or `python scripts/validate_trl5.py`) to produce the final signed-off `docs/trl5/validation_report.md`. That report is intentionally not committed until a clean run exists.
- Latency was measured against Docker Desktop on Windows, where each database round trip costs 15-50 ms; a Linux host will be faster.
- The synthetic generator now embeds a known readmission signal so the ML stack can be checked for learnability. The AUC proves the machinery works, not clinical accuracy.

**Defects found and fixed by this validation** (none were visible to the unit tests): invalid `:param::jsonb` SQL in four modules; ETL crashes on extra tables and int-to-boolean flags; duplicate `admission_id` columns breaking two ML models; HTTP 403 instead of 401 for missing credentials; audit rows dropped for non-IP client hosts; blocking database and Redis I/O on the async event loop in three middlewares; ambiguous primary-tenant seed data.

## 5. What TRL 5 does NOT claim

- Data is **synthetic**. Real hospital data (de-identified or under an agreement) is the TRL 6 step.
- Readmission AUC on synthetic data demonstrates that the pipeline works, not clinical accuracy.
- Not a cleared medical device (no FDA/CE/Iranian MoH clearance claimed).
- CAD imaging, genomics and wearables remain stubs/roadmap and are outside this validation.
- Single-node Docker, not a multi-node production cluster.

## 6. Path to TRL 6 (next)

1. Pilot deployment at one hospital on de-identified data; measure model AUC/calibration on real labels.
2. External security review / penetration test; HIPAA/GDPR/local-regulation gap assessment.
3. Clinician usability study on the dashboard and alerts.
4. Regulatory classification (software-as-medical-device) and quality system plan.
