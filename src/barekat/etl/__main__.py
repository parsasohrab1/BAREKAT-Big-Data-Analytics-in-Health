"""ETL pipeline CLI entry point."""

import argparse

from barekat.etl.pipeline import ETLPipeline


def main():
    parser = argparse.ArgumentParser(description="BAREKAT ETL Pipeline")
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="Load mode: incremental (default) or full reload",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip Great Expectations schema validation",
    )
    args = parser.parse_args()

    pipeline = ETLPipeline()
    result = pipeline.run(mode=args.mode, skip_validation=args.skip_validation)
    print(f"ETL completed: run_id={result['run_id']}, mode={result['mode']}")
    print(f"Records loaded: {result['records_loaded']}")
    print(f"Validation: {'passed' if result['validation']['success'] else 'failed'}")
    print(f"Quality checks: {result['quality_checks']}")
    return result


if __name__ == "__main__":
    main()
