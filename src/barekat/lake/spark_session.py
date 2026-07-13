"""Spark session factory with MinIO S3A and Delta/Iceberg support."""

from __future__ import annotations

from barekat.config.settings import get_settings


def get_spark_session(app_name: str = "barekat-lake"):
    """Create SparkSession configured for MinIO Data Lake.

    Requires pyspark (+ delta-spark or iceberg-spark-runtime) installed.
    """
    try:
        from pyspark.sql import SparkSession
    except ImportError as exc:
        raise RuntimeError(
            "pyspark not installed. pip install pyspark delta-spark "
            "or use pandas fallback in lake.batch modules."
        ) from exc

    settings = get_settings()
    endpoint = settings.minio_endpoint
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", settings.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", str(settings.minio_secure).lower())
    )

    if settings.spark_master_url:
        builder = builder.master(settings.spark_master_url)

    fmt = settings.lake_table_format.lower()

    if fmt == "delta":
        builder = (
            builder
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        )
    elif fmt == "iceberg":
        warehouse = f"s3a://{settings.minio_bucket_lake}/{settings.lake_silver_prefix}/"
        builder = (
            builder
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config("spark.sql.catalog.lake", "org.apache.iceberg.spark.SparkCatalog")
            .config("spark.sql.catalog.lake.type", "hadoop")
            .config("spark.sql.catalog.lake.warehouse", warehouse)
            .config("spark.hadoop.fs.s3a.endpoint", endpoint)
        )

    return builder.getOrCreate()


def write_table(df, path: str, *, mode: str = "overwrite", partition_by: list[str] | None = None):
    """Write DataFrame using configured table format (delta/iceberg/parquet)."""
    settings = get_settings()
    fmt = settings.lake_table_format.lower()
    writer = df.write.mode(mode)
    if partition_by:
        writer = writer.partitionBy(*partition_by)

    if fmt == "delta":
        writer.format("delta").save(path)
    elif fmt == "iceberg":
        table_path = path.replace("s3a://", "").split("/", 1)[-1]
        df.createOrReplaceTempView("_lake_tmp")
        spark = df.sparkSession
        spark.sql(f"CREATE TABLE IF NOT EXISTS lake.`{table_path.replace('/', '_')}` USING iceberg LOCATION '{path}'")
        writer.format("iceberg").save(path)
    else:
        writer.parquet(path)


def read_table(spark, path: str, fmt: str | None = None):
    """Read table from lake path."""
    settings = get_settings()
    table_fmt = (fmt or settings.lake_table_format).lower()
    if table_fmt == "delta":
        return spark.read.format("delta").load(path)
    if table_fmt == "iceberg":
        return spark.read.format("iceberg").load(path)
    return spark.read.parquet(path)
