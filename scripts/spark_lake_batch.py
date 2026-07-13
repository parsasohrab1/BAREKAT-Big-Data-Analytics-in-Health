#!/usr/bin/env python3
"""Submit Spark batch job: bronze → silver → gold on MinIO Data Lake."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    parser = argparse.ArgumentParser(description="BAREKAT Data Lake Spark batch")
    parser.add_argument("--step", choices=["full", "silver", "gold"], default="full")
    args = parser.parse_args()

    from barekat.config.settings import get_settings
    settings = get_settings()
    if not settings.lake_spark_enabled:
        print("Set LAKE_SPARK_ENABLED=true for Spark batch jobs")

    if args.step == "full":
        from barekat.lake.pipeline import LakePipeline
        result = LakePipeline().run_full()
    elif args.step == "silver":
        from barekat.lake.batch.bronze_to_silver import run_bronze_to_silver
        result = run_bronze_to_silver()
    else:
        from barekat.lake.batch.silver_to_gold import run_silver_to_gold
        result = run_silver_to_gold()

    print(result)


if __name__ == "__main__":
    main()
