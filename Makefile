.PHONY: help setup infra up down generate-data etl train api dashboard test clean

help:
	@echo "BAREKAT Health Analytics - Available commands:"
	@echo "  make setup          - Install Python dependencies"
	@echo "  make infra          - Start infrastructure services (Docker)"
	@echo "  make up             - Start all services"
	@echo "  make down           - Stop all services"
	@echo "  make generate-data  - Generate synthetic health data"
	@echo "  make etl            - Run ETL pipeline"
	@echo "  make train          - Train ML models"
	@echo "  make api            - Start API server locally"
	@echo "  make dashboard      - Start Streamlit dashboard"
	@echo "  make test           - Run tests"
	@echo "  make clean          - Clean generated data"

setup:
	pip install -r requirements.txt
	pip install -e .

infra:
	docker compose up -d postgres minio redis zookeeper kafka spark-master spark-worker

up:
	docker compose up -d

down:
	docker compose down

generate-data:
	python scripts/generate_data.py --patients 1000 --admissions 3000 --output ./data/raw

etl:
	python -m barekat.etl.pipeline

train:
	python -m barekat.ml.pipeline

api:
	uvicorn barekat.api.main:app --reload --host 0.0.0.0 --port 8000

dashboard:
	streamlit run dashboards/app.py --server.port 8501

test:
	pytest tests/ -v

clean:
	rm -rf data/raw/*.csv data/processed/* data/models/*
