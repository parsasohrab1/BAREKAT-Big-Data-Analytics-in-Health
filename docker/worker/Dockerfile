FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY pyproject.toml .
RUN pip install -e .

ENV PYTHONPATH=/app/src

CMD ["celery", "-A", "barekat.worker.celery_app:celery_app", "worker", "--loglevel=info", "--concurrency=2"]
