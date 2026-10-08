# TRL 5 validation runner: clean Python 3.12 environment matching the production images (3.11 satisfies requires-python).
# The repository is mounted at /app at run time (see `make validate-trl5`).
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 60 -r requirements.txt

ENV PYTHONPATH=/app/src:/app
CMD ["python", "scripts/validate_trl5.py"]
