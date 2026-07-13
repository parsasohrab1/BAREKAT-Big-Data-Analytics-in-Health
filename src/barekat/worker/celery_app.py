"""Celery application for scheduled ETL jobs."""

from celery import Celery
from celery.schedules import crontab

from barekat.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "barekat",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["barekat.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.conf.beat_schedule = {
    "etl-incremental-hourly": {
        "task": "barekat.worker.tasks.run_etl_incremental",
        "schedule": crontab(minute=settings.etl_incremental_minute),
    },
    "etl-full-daily": {
        "task": "barekat.worker.tasks.run_etl_full",
        "schedule": crontab(
            hour=settings.etl_full_hour,
            minute=settings.etl_full_minute,
        ),
    },
    "ml-retrain-weekly": {
        "task": "barekat.worker.tasks.run_ml_retrain",
        "schedule": crontab(
            day_of_week=settings.ml_retrain_day_of_week,
            hour=settings.ml_retrain_hour,
            minute=settings.ml_retrain_minute,
        ),
    },
    "retention-purge-daily": {
        "task": "barekat.worker.tasks.run_retention_purge",
        "schedule": crontab(
            hour=settings.retention_purge_hour,
            minute=settings.retention_purge_minute,
        ),
    },
    "weekly-reports": {
        "task": "barekat.worker.tasks.run_weekly_reports",
        "schedule": crontab(
            day_of_week=settings.weekly_report_day_of_week,
            hour=settings.weekly_report_hour,
            minute=settings.weekly_report_minute,
        ),
    },
    "lake-batch-weekly": {
        "task": "barekat.worker.tasks.run_lake_batch",
        "schedule": crontab(
            day_of_week=settings.lake_batch_day_of_week,
            hour=settings.lake_batch_hour,
            minute=settings.lake_batch_minute,
        ),
        "kwargs": {"mode": "full"},
    },
    "drift-check-daily": {
        "task": "barekat.worker.tasks.run_drift_check",
        "schedule": crontab(
            hour=settings.drift_check_hour,
            minute=settings.drift_check_minute,
        ),
    },
}
