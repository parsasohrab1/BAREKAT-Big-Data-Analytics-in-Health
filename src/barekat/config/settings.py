"""Application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    barekat_env: str = "development"
    api_port: int = 8000
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "barekat"
    postgres_password: str = "barekat_secret"
    postgres_db: str = "barekat_health"

    redis_host: str = "localhost"
    redis_port: int = 6379

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "barekat_minio"
    minio_secret_key: str = "barekat_minio_secret"
    minio_bucket_raw: str = "health-raw"
    minio_bucket_processed: str = "health-processed"
    minio_secure: bool = False

    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_admissions: str = "health.admissions"
    kafka_topic_lab_results: str = "health.lab_results"
    kafka_topic_alerts: str = "health.alerts"

    spark_master_url: str = "spark://localhost:7077"

    data_raw_path: str = "./data/raw"
    data_processed_path: str = "./data/processed"
    data_models_path: str = "./data/models"

    ml_readmission_threshold: float = 0.7
    ml_cluster_count: int = 5

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
