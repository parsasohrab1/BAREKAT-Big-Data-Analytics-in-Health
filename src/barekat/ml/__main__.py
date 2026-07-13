"""ML pipeline CLI entry point."""

import argparse

from barekat.ml.pipeline import MLPipeline


def main():
    parser = argparse.ArgumentParser(description="BAREKAT ML Pipeline")
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Retrain using latest data from PostgreSQL (or CSV fallback)",
    )
    args = parser.parse_args()

    ml = MLPipeline()
    if args.retrain:
        results = ml.retrain()
        print("ML retrain completed (latest data)")
    else:
        results = ml.run_all()
        print("ML training completed")

    print(f"Readmission: {results.get('readmission')}")
    print(f"Clustering: {results.get('clustering')}")
    print(f"Alerts: {results.get('alerts_generated')} generated, {results.get('alerts_persisted')} persisted")


if __name__ == "__main__":
    main()
