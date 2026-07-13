"""Celery tasks for ETL scheduling with retry."""

from __future__ import annotations

import structlog

from barekat.config.settings import get_settings
from barekat.etl.pipeline import ETLPipeline
from barekat.etl.run_logger import mark_retrying
from barekat.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)
settings = get_settings()


@celery_app.task(
    bind=True,
    name="barekat.worker.tasks.run_etl_incremental",
    max_retries=settings.etl_max_retries,
    default_retry_delay=settings.etl_retry_delay_seconds,
)
def run_etl_incremental(self) -> dict:
    return _execute_etl(self, mode="incremental")


@celery_app.task(
    bind=True,
    name="barekat.worker.tasks.run_etl_full",
    max_retries=settings.etl_max_retries,
    default_retry_delay=settings.etl_retry_delay_seconds,
)
def run_etl_full(self) -> dict:
    return _execute_etl(self, mode="full")


@celery_app.task(
    bind=True,
    name="barekat.worker.tasks.run_ml_retrain",
    max_retries=settings.ml_max_retries,
    default_retry_delay=settings.etl_retry_delay_seconds,
)
def run_ml_retrain(self) -> dict:
    retry_count = self.request.retries
    try:
        from barekat.ml.pipeline import MLPipeline

        logger.info("ml_retrain_started", task_id=self.request.id, retry=retry_count)
        results = MLPipeline().retrain()
        logger.info("ml_retrain_completed", version=results.get("readmission", {}).get("version"))
        return {"status": "success", "results": results}
    except Exception as exc:
        logger.error("ml_retrain_failed", error=str(exc), retry=retry_count)
        raise self.retry(exc=exc)


@celery_app.task(name="barekat.worker.tasks.run_retention_purge")
def run_retention_purge() -> dict:
    from barekat.privacy.retention import purge_expired_data

    logger.info("retention_purge_started")
    result = purge_expired_data(triggered_by="celery_beat")
    logger.info("retention_purge_completed", status=result.get("status"))
    return result


@celery_app.task(name="barekat.worker.tasks.run_weekly_reports")
def run_weekly_reports() -> dict:
    from barekat.services.reports import list_tenant_ids, send_weekly_report_to_managers

    logger.info("weekly_reports_started")
    results = []
    for tenant_id in list_tenant_ids():
        try:
            result = send_weekly_report_to_managers(tenant_id)
            results.append(result)
            logger.info("weekly_report_sent", tenant_id=tenant_id, emails=result.get("emails_sent"))
        except Exception as exc:
            logger.error("weekly_report_failed", tenant_id=tenant_id, error=str(exc))
            results.append({"tenant_id": tenant_id, "status": "failed", "error": str(exc)})
    return {"status": "completed", "tenants": len(results), "results": results}


@celery_app.task(name="barekat.worker.tasks.send_alert_notification")
def send_alert_notification(alert: dict, tenant_id: str = "default") -> dict:
    from barekat.services.notifications import dispatch_critical_alert

    sent = dispatch_critical_alert(alert, tenant_id=tenant_id)
    return {"tenant_id": tenant_id, "sent": sent}


@celery_app.task(name="barekat.worker.tasks.run_lake_batch")
def run_lake_batch(mode: str = "full") -> dict:
    from barekat.lake.pipeline import LakePipeline

    logger.info("lake_batch_started", mode=mode)
    pipeline = LakePipeline()
    if mode == "incremental":
        result = pipeline.run_incremental()
    else:
        result = pipeline.run_full()
    logger.info("lake_batch_completed", steps=result.get("steps"))
    return result


@celery_app.task(name="barekat.worker.tasks.run_drift_check")
def run_drift_check() -> dict:
    from barekat.observability.drift import check_all_models
    from barekat.observability.exporter import refresh_metrics_from_db

    logger.info("drift_check_started")
    results = check_all_models()
    refresh_metrics_from_db()
    drifted = [r for r in results if r.get("drift_detected")]
    if drifted:
        logger.warning("drift_check_alerts", models=[d["model_name"] for d in drifted])
    return {"checked": len(results), "drift_detected": drifted}


def _execute_etl(task, mode: str) -> dict:
    retry_count = task.request.retries
    pipeline = ETLPipeline()

    try:
        logger.info("etl_started", mode=mode, task_id=task.request.id, retry=retry_count)
        result = pipeline.run(
            mode=mode,
            celery_task_id=task.request.id,
            retry_count=retry_count,
        )
        logger.info("etl_completed", run_id=result["run_id"], mode=mode)
        return result
    except Exception as exc:
        logger.error("etl_failed", mode=mode, error=str(exc), retry=retry_count)
        if hasattr(task, "request") and task.request.id:
            try:
                from barekat.etl.run_logger import get_recent_runs
                recent = get_recent_runs(limit=1)
                if recent:
                    mark_retrying(recent[0]["run_id"], retry_count + 1, str(exc))
            except Exception:
                pass
        raise task.retry(exc=exc)
