"""TRL 5 validation harness: exercises the integrated stack against pre-declared acceptance criteria.

Runs against real PostgreSQL, Redis, MinIO and Kafka (see `make validate-trl5`) and writes
docs/trl5/validation_report.{json,md}. Exit code is non-zero if any gate fails.
"""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Acceptance criteria (declared before running; see docs/TRL5_VALIDATION.md)
CRITERIA = {
    "n_patients": int(os.getenv("VALIDATE_PATIENTS", "5000")),
    "n_admissions": int(os.getenv("VALIDATE_ADMISSIONS", "15000")),
    "etl_min_rows_per_sec": 500,
    "api_p95_ms": 500,
    "api_requests": 200,
    "api_concurrency": 10,
    "readmission_min_auc": 0.60,
    "kafka_roundtrip_s": 15,
}

RESULTS: list[dict] = []
CTX: dict = {}


def stage(name: str):
    def deco(fn):
        def run():
            t0 = time.monotonic()
            rec = {"stage": name, "passed": False, "metrics": {}, "error": None}
            try:
                rec["metrics"] = fn() or {}
                rec["passed"] = True
            except Exception as exc:  # noqa: BLE001
                rec["error"] = f"{type(exc).__name__}: {exc}"
                rec["trace"] = traceback.format_exc(limit=4)
            rec["seconds"] = round(time.monotonic() - t0, 2)
            RESULTS.append(rec)
            print(f"[{'PASS' if rec['passed'] else 'FAIL'}] {name} ({rec['seconds']}s) {rec['error'] or ''}", flush=True)
        return run
    return deco


@stage("S1 infrastructure reachable (PostgreSQL, Redis, MinIO, Kafka)")
def s1():
    import redis
    from confluent_kafka.admin import AdminClient
    from minio import Minio
    from sqlalchemy import text

    from barekat.config.settings import get_settings
    from barekat.storage.database import engine

    s = get_settings()
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    redis.Redis(host=s.redis_host, port=s.redis_port).ping()
    Minio(s.minio_endpoint, access_key=s.minio_access_key, secret_key=s.minio_secret_key, secure=False).list_buckets()
    topics = AdminClient({"bootstrap.servers": s.kafka_bootstrap_servers}).list_topics(timeout=10)
    return {"kafka_brokers": len(topics.brokers)}


@stage("S2 schema + migrations apply idempotently")
def s2():
    from scripts.apply_init_sql import apply_init_sql

    apply_init_sql()
    apply_init_sql()  # second run must be a no-op, not an error
    return {"applied_twice": True}


@stage("S3 ETL at scale: full load, validation on, idempotent re-run")
def s3():
    from sqlalchemy import text

    from barekat.config.settings import get_settings
    from barekat.etl.pipeline import ETLPipeline
    from barekat.storage.database import engine
    from scripts.generate_data import generate_healthcare_big_data, save_to_csv

    raw = Path(tempfile.mkdtemp(prefix="trl5_raw_"))
    data = generate_healthcare_big_data(CRITERIA["n_patients"], CRITERIA["n_admissions"])
    save_to_csv(data, raw)
    CTX["data"] = data
    os.environ["DATA_RAW_PATH"] = str(raw)
    get_settings.cache_clear()

    total_in = sum(len(df) for df in data.values())
    try:
        import great_expectations  # noqa: F401
        ge_ok = True
    except ImportError:
        ge_ok = False  # recorded in the report; schema validation then NOT part of this evidence
    t0 = time.monotonic()
    res = ETLPipeline().run(mode="full", skip_validation=not ge_ok)
    dt = time.monotonic() - t0
    rate = total_in / dt

    def count(tbl):
        with engine.connect() as c:
            return c.execute(text(f"SELECT COUNT(*) FROM raw.{tbl}")).scalar()

    patients, admissions = count("patients"), count("admissions")
    assert patients == len(data["Patients"]), f"patients {patients} != {len(data['Patients'])}"
    assert admissions == len(data["Admissions"]), f"admissions {admissions} != {len(data['Admissions'])}"
    assert all(q["passed"] for q in res["quality_checks"].values()), res["quality_checks"]
    assert rate >= CRITERIA["etl_min_rows_per_sec"], f"{rate:.0f} rows/s below gate"

    ETLPipeline().run(mode="incremental", skip_validation=not ge_ok)
    assert count("patients") == patients and count("admissions") == admissions, "re-run duplicated rows"
    return {"rows_in": total_in, "seconds": round(dt, 2), "rows_per_sec": round(rate), "idempotent": True,
            "great_expectations": "on" if ge_ok else "SKIPPED (not installed)"}


@stage("S4 data lake Bronze/Silver/Gold on MinIO")
def s4():
    from barekat.lake.pipeline import LakePipeline

    res = LakePipeline().run_full()
    assert res.get("status") == "success", res
    tables = LakePipeline().status().get("tables", [])
    assert tables, "no lake tables catalogued"
    return {"steps": res["steps"], "tables": len(tables)}


@stage("S5 ML training, registry and AUC gate")
def s5():
    from barekat.ml.pipeline import MLPipeline
    from barekat.ml.registry import list_models

    res = MLPipeline().run_all(CTX["data"])
    models = list_models(limit=50)
    assert models, "no models registered"
    auc = res["readmission"].get("test_auc")  # held-out split, not training AUC
    CTX["auc"] = auc
    assert auc is not None and auc >= CRITERIA["readmission_min_auc"], f"readmission AUC {auc} below gate"
    return {"readmission_auc": auc, "models_registered": len(models), "alerts": res["alerts_generated"]}


def _start_api():
    env = dict(os.environ, BAREKAT_ENV="staging", JWT_SECRET=os.getenv("JWT_SECRET", "trl5-validation-secret"),
               PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
               # load test comes from one client IP; the general limit is raised for it (login limit is left default)
               RATE_LIMIT_PER_MINUTE="100000")
    log = open(ROOT / "docs" / "trl5" / "api.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "barekat.api.main:app", "--port", "8765", "--host", "127.0.0.1"],
        env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    import httpx

    for _ in range(40):
        if proc.poll() is not None:
            raise RuntimeError(f"API exited early (code {proc.returncode}); see docs/trl5/api.log")
        try:
            if httpx.get("http://127.0.0.1:8765/health", timeout=2).status_code == 200:
                return proc
        except Exception:  # noqa: BLE001
            time.sleep(1)
    proc.kill()
    raise RuntimeError("API did not start within 40s; see docs/trl5/api.log")


def _login(client, user, pw):
    r = client.post("/api/v1/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200, f"login {user}: {r.status_code} {r.text[:120]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@stage("S6 live API: auth, RBAC, data consistency, latency under load")
def s6():
    import httpx

    proc = _start_api()
    CTX["api"] = proc
    try:
        c = httpx.Client(base_url="http://127.0.0.1:8765", timeout=30)
        assert c.get("/api/v1/analytics/summary").status_code in (401, 403), "unauthenticated access allowed"
        admin = _login(c, "admin", "admin123")
        CTX["admin"] = admin  # reused by S7: the login endpoint is rate limited by design
        assert c.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        summ = c.get("/api/v1/analytics/summary", headers=admin).json()["summary"]
        assert summ["total_patients"] == CRITERIA["n_patients"], summ
        assert c.get("/ready").json()["status"] == "ready"
        clin = _login(c, "clinician", "clinician123")
        assert c.post("/api/v1/ml/retrain", headers=clin).status_code == 403, "RBAC not enforced"

        n, conc = CRITERIA["api_requests"], CRITERIA["api_concurrency"]
        lat: list[float] = []

        def hit(i):
            cl = httpx.Client(base_url="http://127.0.0.1:8765", timeout=30)
            path = "/api/v1/analytics/summary" if i % 2 else "/api/v1/patients/"
            t = time.perf_counter()
            r = cl.get(path, headers=admin)
            lat.append((time.perf_counter() - t) * 1000)
            return r.status_code

        with ThreadPoolExecutor(conc) as ex:
            codes = list(ex.map(hit, range(n)))
        ok = sum(1 for x in codes if x == 200)
        p95 = statistics.quantiles(lat, n=100)[94]
        assert ok == n, f"{n - ok} requests failed: {set(codes)}"
        assert p95 <= CRITERIA["api_p95_ms"], f"p95 {p95:.0f}ms above gate"
        attempts = [c.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code
                    for _ in range(15)]
        assert 429 in attempts, f"login brute-force not throttled: {set(attempts)}"
        return {"requests": n, "concurrency": conc, "p50_ms": round(statistics.median(lat)), "p95_ms": round(p95),
                "login_throttled_after": attempts.index(429)}
    except Exception:
        proc.kill()
        CTX.pop("api", None)
        raise


@stage("S7 streaming: HL7 ingest -> Kafka round trip, invalid input rejected")
def s7():
    import uuid

    import httpx
    from confluent_kafka import Consumer

    from barekat.config.settings import get_settings

    s = get_settings()
    c = httpx.Client(base_url="http://127.0.0.1:8765", timeout=30)
    admin = CTX["admin"]
    # earliest + unique event_id match: robust to the topic being auto-created by the first publish
    cons = Consumer({"bootstrap.servers": s.kafka_bootstrap_servers, "group.id": f"trl5-{uuid.uuid4()}",
                     "auto.offset.reset": "earliest", "topic.metadata.refresh.interval.ms": 1000})
    cons.subscribe([s.kafka_topic_hl7])
    msg = ("MSH|^~\\&|MONITOR|ICU|BAREKAT|HOSP|20260713090000||ORU^R01|TRL5MSG1|P|2.5\r"
           "PID|1||PT00001^^^HOSP||DOE^JOHN\rOBR|1|||VITALS^VITAL SIGNS\r"
           "OBX|1|NM|8867-4^Heart Rate||112|bpm\rOBX|2|NM|2708-6^SpO2||91|%")
    t0 = time.monotonic()
    r = c.post("/api/v1/ingest/hl7", json={"message": msg}, headers=admin)
    assert r.status_code == 200, r.text
    event_id = r.json()["event_id"]
    got = None
    while time.monotonic() - t0 < CRITERIA["kafka_roundtrip_s"]:
        m = cons.poll(1.0)
        if m and not m.error() and event_id in m.value().decode():
            got = time.monotonic() - t0
            break
    cons.close()
    assert got is not None, "event not seen on Kafka"
    assert c.post("/api/v1/ingest/hl7", json={"message": "not an hl7 message"}, headers=admin).status_code == 400
    return {"roundtrip_s": round(got, 2)}


@stage("S8 compliance + observability: audit trail written, Prometheus metrics served")
def s8():
    import httpx
    from sqlalchemy import text

    from barekat.storage.database import engine

    c = httpx.Client(base_url="http://127.0.0.1:8765", timeout=30)
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM audit.access_logs")).scalar()
    assert n and n > 0, "no audit records written by API traffic"
    body = c.get("/metrics").text
    assert "barekat" in body or "http_request" in body, "no application metrics exposed"
    return {"audit_rows": n, "metrics_bytes": len(body)}


@stage("S9 automated test suite incl. integration tests")
def s9():
    p = subprocess.run([sys.executable, "-m", "pytest", "tests", "-m", "", "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-200:]
    assert p.returncode == 0, tail
    return {"summary": tail}


def write_report() -> bool:
    out = ROOT / "docs" / "trl5"
    ok = all(r["passed"] for r in RESULTS)
    report = {"generated": datetime.now(timezone.utc).isoformat(), "criteria": CRITERIA,
              "overall": "PASS" if ok else "FAIL", "stages": RESULTS}
    (out / "validation_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = [f"# TRL 5 validation report — {report['overall']}", "", f"Generated: {report['generated']}", "",
             "| Stage | Result | Time | Metrics / error |", "|---|---|---|---|"]
    for r in RESULTS:
        detail = r["error"] or ", ".join(f"{k}={v}" for k, v in r["metrics"].items())
        lines.append(f"| {r['stage']} | {'PASS' if r['passed'] else 'FAIL'} | {r['seconds']}s | {detail} |")
    (out / "validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ok


def main() -> int:
    (ROOT / "docs" / "trl5").mkdir(parents=True, exist_ok=True)
    for fn in (s1, s2, s3, s4, s5):
        fn()
    s6()
    if "api" in CTX:
        s7()
        s8()
        CTX["api"].terminate()
    s9()
    return 0 if write_report() else 1


if __name__ == "__main__":
    sys.exit(main())
