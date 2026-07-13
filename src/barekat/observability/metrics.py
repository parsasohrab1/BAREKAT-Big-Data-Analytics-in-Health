"""Prometheus metrics for BAREKAT services."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Info

# HTTP (populated by middleware)
HTTP_REQUESTS = Counter(
    "barekat_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "barekat_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ETL
ETL_RUNS = Counter(
    "barekat_etl_runs_total",
    "ETL pipeline runs",
    ["mode", "status"],
)
ETL_LAST_SUCCESS = Gauge(
    "barekat_etl_last_success_timestamp",
    "Unix timestamp of last successful ETL run",
    ["mode"],
)
ETL_DURATION = Histogram(
    "barekat_etl_duration_seconds",
    "ETL run duration",
    ["mode"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1800),
)

# ML models
ML_MODEL_AUC = Gauge(
    "barekat_ml_model_auc",
    "Active model AUC-ROC",
    ["model_name"],
)
ML_MODEL_F1 = Gauge(
    "barekat_ml_model_f1",
    "Active model F1 score",
    ["model_name"],
)
ML_DRIFT_PSI = Gauge(
    "barekat_ml_drift_psi",
    "Population Stability Index vs baseline",
    ["model_name"],
)
ML_DRIFT_DETECTED = Gauge(
    "barekat_ml_drift_detected",
    "1 if model drift detected",
    ["model_name"],
)
ML_AUC_DROP = Gauge(
    "barekat_ml_auc_drop",
    "AUC drop from baseline",
    ["model_name"],
)

# Alerts & lake
ACTIVE_ALERTS = Gauge(
    "barekat_active_alerts",
    "Unacknowledged predictive alerts",
    ["severity"],
)
LAKE_JOB_STATUS = Gauge(
    "barekat_lake_job_last_success",
    "1 if last lake job succeeded",
    ["job_name"],
)

# Service info
SERVICE_INFO = Info("barekat_service", "BAREKAT platform info")


def record_etl_run(mode: str, status: str, duration_sec: float | None = None) -> None:
    ETL_RUNS.labels(mode=mode, status=status).inc()
    if status == "success" and duration_sec is not None:
        ETL_DURATION.labels(mode=mode).observe(duration_sec)


def record_ml_metrics(model_name: str, metrics: dict) -> None:
    if metrics.get("auc") is not None:
        ML_MODEL_AUC.labels(model_name=model_name).set(float(metrics["auc"]))
    if metrics.get("f1") is not None:
        ML_MODEL_F1.labels(model_name=model_name).set(float(metrics["f1"]))


def record_drift(model_name: str, psi: float, auc_drop: float, detected: bool) -> None:
    ML_DRIFT_PSI.labels(model_name=model_name).set(psi)
    ML_AUC_DROP.labels(model_name=model_name).set(auc_drop)
    ML_DRIFT_DETECTED.labels(model_name=model_name).set(1 if detected else 0)
