.PHONY: help setup infra observability-up up down staging-up prod-up secure-up db-migrate generate-data sample-dicom ingest-dicom etl etl-full lake lake-spark worker beat faust stream-simulate train api dashboard test test-integration lint clean secrets tls-certs

help:
	@echo "BAREKAT Health Analytics - Available commands:"
	@echo "  make setup              - Install Python dependencies"
	@echo "  make infra              - Start infrastructure services (Docker)"
	@echo "  make observability-up   - Start Prometheus + Grafana + Loki stack"
	@echo "  make up                 - Start all services (development)"
	@echo "  make staging-up         - Start staging stack"
	@echo "  make prod-up            - Start production stack"
	@echo "  make db-migrate         - Apply pending PostgreSQL migrations"
	@echo "  make secure-up          - Production + TLS + Docker Secrets + WAF"
	@echo "  make secrets            - Generate Docker Secrets files"
	@echo "  make tls-certs          - Generate self-signed TLS certificates"
	@echo "  make down               - Stop all services"
	@echo "  make generate-data      - Generate synthetic health data"
	@echo "  make sample-dicom       - Generate sample DICOM studies"
	@echo "  make ingest-dicom       - Ingest ./data/dicom into MinIO + PostgreSQL"
	@echo "  make etl                - Run incremental ETL pipeline"
	@echo "  make etl-full           - Run full ETL reload"
	@echo "  make lake               - Run Data Lake pipeline (Bronze/Silver/Gold)"
	@echo "  make lake-spark         - Spark batch on MinIO (requires pyspark)"
	@echo "  make worker             - Start Celery worker locally"
	@echo "  make beat               - Start Celery Beat scheduler locally"
	@echo "  make faust              - Start Faust stream processor locally"
	@echo "  make stream-simulate    - Simulate HL7/FHIR events (needs JWT token)"
	@echo "  make train              - Train ML models"
	@echo "  make api                - Start API server locally"
	@echo "  make dashboard          - Start Streamlit dashboard"
	@echo "  make lint               - Run ruff linter"
	@echo "  make test               - Run unit tests"
	@echo "  make test-integration   - Run integration tests (requires PostgreSQL)"
	@echo "  make clean              - Clean generated data"

setup:
	pip install -r requirements.txt
	pip install -e .

infra:
	docker compose up -d postgres minio redis zookeeper kafka spark-master spark-worker

observability-up:
	docker compose -f docker-compose.yml -f docker-compose.observability.yml up -d prometheus grafana loki promtail alertmanager redis-exporter postgres-exporter

up:
	docker compose up -d

staging-up:
	docker compose -f docker-compose.staging.yml --env-file .env.staging up -d --build

prod-up:
	docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

secrets:
	bash scripts/setup_secrets.sh

tls-certs:
	bash scripts/generate_tls_certs.sh

secure-up: secrets tls-certs
	docker compose -f docker-compose.prod.yml -f docker-compose.secure.yml --env-file .env.production up -d --build

db-migrate:
	python scripts/apply_migrations.py

down:
	docker compose down

generate-data:
	python scripts/generate_data.py --patients 1000 --admissions 3000 --output ./data/raw

sample-dicom:
	python scripts/generate_sample_dicom.py --output ./data/dicom --count 5

ingest-dicom:
	python -c "from pathlib import Path; from barekat.imaging.store import ingest_directory; ingest_directory(Path('./data/dicom'))"

etl:
	python -m barekat.etl.pipeline --mode incremental

etl-full:
	python -m barekat.etl.pipeline --mode full

lake:
	python -c "from barekat.lake.pipeline import LakePipeline; import json; print(json.dumps(LakePipeline().run_full(), default=str, indent=2))"

lake-spark:
	LAKE_SPARK_ENABLED=true python scripts/spark_lake_batch.py --step full

worker:
	celery -A barekat.worker.celery_app:celery_app worker --loglevel=info

beat:
	celery -A barekat.worker.celery_app:celery_app beat --loglevel=info

faust:
	faust -A barekat.streaming.faust_app:app worker -l info

stream-simulate:
	@echo "Usage: python scripts/simulate_stream.py --token <JWT>"

train:
	python -m barekat.ml.pipeline

train-retrain:
	python -m barekat.ml.pipeline --retrain

api:
	uvicorn barekat.api.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	streamlit run dashboards/app.py --server.port 8501

test:
	pytest tests/ -v --ignore=tests/integration

test-integration:
	pytest tests/integration -v -m integration

lint:
	ruff check src tests scripts dashboards

clean:
	rm -rf data/raw/*.csv data/processed/* data/models/*
