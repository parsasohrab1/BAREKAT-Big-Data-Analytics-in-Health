"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    barekat_env: str = "development"
    api_port: int = 8000
    jwt_expire_minutes: int = 60

    # Authentication
    auth_use_database: bool = True
    auth_dev_fallback: bool = True
    db_auto_migrate: bool = True
    cors_origins: str = "*"  # comma-separated origins in production

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "barekat"
    postgres_db: str = "barekat_health"

    redis_host: str = "localhost"
    redis_port: int = 6379

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "barekat_minio"
    minio_bucket_raw: str = "health-raw"
    minio_bucket_processed: str = "health-processed"
    minio_bucket_lake: str = "health-lake"
    minio_secure: bool = False

    # Data Lake (Bronze / Silver / Gold on MinIO)
    lake_enabled: bool = True
    lake_table_format: str = "delta"  # delta | iceberg | parquet
    lake_bronze_prefix: str = "bronze"
    lake_silver_prefix: str = "silver"
    lake_gold_prefix: str = "gold"
    lake_spark_enabled: bool = False
    lake_batch_day_of_week: int = 0  # Monday
    lake_batch_hour: int = 1
    lake_batch_minute: int = 0

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_admissions: str = "health.admissions"
    kafka_topic_lab_results: str = "health.lab_results"
    kafka_topic_alerts: str = "health.alerts"
    kafka_topic_events_raw: str = "health.events.raw"
    kafka_topic_hl7: str = "health.hl7"
    kafka_topic_fhir: str = "health.fhir"

    redis_alerts_channel: str = "barekat:alerts:live"
    redis_alerts_recent_key: str = "barekat:alerts:recent"
    redis_alerts_recent_max: int = 200

    pacs_host: str = "localhost"
    pacs_port: int = 4242
    pacs_ae_title: str = "ORTHANC"
    pacs_calling_ae: str = "BAREKAT"
    pacs_orthanc_url: str = ""  # e.g. http://localhost:8042

    spark_master_url: str = "spark://localhost:7077"

    data_raw_path: str = "./data/raw"
    data_processed_path: str = "./data/processed"
    data_models_path: str = "./data/models"

    ml_readmission_threshold: float = 0.7
    ml_cluster_count: int = 5

    dashboard_data_source: str = "auto"  # auto | postgres | csv

    etl_max_retries: int = 3
    etl_retry_delay_seconds: int = 60
    etl_incremental_minute: int = 0
    etl_full_hour: int = 2
    etl_full_minute: int = 0

    ml_retrain_day_of_week: int = 0  # Monday
    ml_retrain_hour: int = 3
    ml_retrain_minute: int = 0
    ml_max_retries: int = 2

    # Compliance & Privacy (HIPAA / GDPR / domestic)
    audit_enabled: bool = True
    audit_log_ip: bool = True
    compliance_framework: str = "all"  # all | hipaa | gdpr | iran
    data_retention_enabled: bool = True
    retention_purge_hour: int = 4
    retention_purge_minute: int = 0
    default_retention_days: int = 2555  # ~7 years fallback
    require_consent_for_research: bool = False

    # Security hardening
    tls_enabled: bool = False
    secrets_backend: str = "env"  # env | docker | vault
    vault_addr: str = ""
    vault_kv_mount: str = "secret"
    vault_secret_path: str = "barekat"
    phi_encryption_enabled: bool = False
    mfa_required_for_admin: bool = True
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 120
    rate_limit_login_per_minute: int = 10
    waf_enabled: bool = True
    force_https_redirect: bool = False

    # Multi-tenancy
    multi_tenancy_enabled: bool = True
    default_tenant_id: str = "default"

    # Notifications (email / SMS)
    notifications_enabled: bool = False
    alert_notify_min_severity: str = "critical"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "barekat@localhost"
    smtp_use_tls: bool = True
    sms_provider: str = "kavenegar"  # kavenegar | twilio
    kavenegar_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Weekly reports (Celery Beat)
    weekly_report_day_of_week: int = 6  # Sunday
    weekly_report_hour: int = 8
    weekly_report_minute: int = 0

    # Mobile PWA
    mobile_pwa_enabled: bool = True
    mobile_api_base_url: str = "http://localhost:8000"

    # Observability (Prometheus / Grafana / Loki)
    observability_enabled: bool = True
    metrics_refresh_seconds: int = 60
    drift_psi_threshold: float = 0.2
    drift_auc_drop_threshold: float = 0.05
    drift_check_hour: int = 5
    drift_check_minute: int = 0

    @property
    def jwt_secret(self) -> str:
        from barekat.config.secrets import get_jwt_secret
        return get_jwt_secret()

    @property
    def postgres_password(self) -> str:
        from barekat.config.secrets import get_postgres_password
        return get_postgres_password()

    @property
    def pseudonymization_salt(self) -> str:
        from barekat.config.secrets import get_pseudonymization_salt
        return get_pseudonymization_salt()

    @property
    def minio_secret_key(self) -> str:
        from barekat.config.secrets import get_minio_secret_key
        return get_minio_secret_key()

    @property
    def celery_broker_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/0"

    @property
    def celery_result_backend(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/1"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_production(self) -> bool:
        return self.barekat_env.lower() == "production"

    @property
    def is_staging(self) -> bool:
        return self.barekat_env.lower() == "staging"

    @property
    def is_development(self) -> bool:
        return self.barekat_env.lower() in ("development", "dev", "local")

    @property
    def cors_origin_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
