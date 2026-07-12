"""ETL pipeline CLI entry point."""

from barekat.etl.pipeline import ETLPipeline


def main():
    pipeline = ETLPipeline()
    counts = pipeline.run()
    quality = pipeline.validate_data_quality()
    print(f"Quality checks: {quality}")
    return counts


if __name__ == "__main__":
    main()
