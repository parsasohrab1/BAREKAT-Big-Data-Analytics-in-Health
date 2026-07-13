"""Apache Spark Structured Streaming — sink to Delta Lake bronze layer on MinIO."""

from __future__ import annotations

from barekat.config.settings import get_settings
from barekat.lake.paths import s3a_uri, stream_bronze_path


def run_streaming_job() -> None:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import col, from_json
    from pyspark.sql.types import MapType, StringType, StructField, StructType

    settings = get_settings()
    schema = StructType([
        StructField("event_id", StringType()),
        StructField("source", StringType()),
        StructField("event_type", StringType()),
        StructField("patient_id", StringType()),
        StructField("admission_id", StringType()),
        StructField("timestamp", StringType()),
        StructField("payload", MapType(StringType(), StringType())),
    ])

    builder = (
        SparkSession.builder.appName("barekat-health-stream")
        .config("spark.hadoop.fs.s3a.endpoint", settings.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", settings.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", settings.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    )

    if settings.lake_table_format == "delta":
        builder = (
            builder
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        )

    spark = builder.getOrCreate()

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", settings.kafka_bootstrap_servers)
        .option("subscribe", settings.kafka_topic_events_raw)
        .load()
    )
    events = (
        raw.selectExpr("CAST(value AS STRING) as json")
        .select(from_json(col("json"), schema).alias("data"))
        .select("data.*")
    )

    sink_path = s3a_uri(stream_bronze_path())
    fmt = "delta" if settings.lake_table_format == "delta" else "parquet"

    query = (
        events.writeStream
        .format(fmt)
        .outputMode("append")
        .option("path", sink_path)
        .option("checkpointLocation", s3a_uri("bronze/stream/_checkpoints"))
        .start()
    )
    query.awaitTermination()


def main() -> None:
    try:
        run_streaming_job()
    except ImportError as exc:
        raise SystemExit(
            "pyspark not installed. pip install -r requirements-spark.txt\n"
            "Or use Faust worker: faust -A barekat.streaming.faust_app:app worker -l info"
        ) from exc


if __name__ == "__main__":
    main()
