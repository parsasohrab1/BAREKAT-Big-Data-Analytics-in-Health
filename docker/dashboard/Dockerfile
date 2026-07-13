FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboards/ ./dashboards/
COPY src/ ./src/
COPY pyproject.toml .
RUN pip install -e .

ENV DATA_DIR=/app/data/raw
ENV MODELS_DIR=/app/data/models
ENV PYTHONPATH=/app/src
EXPOSE 8501

CMD ["streamlit", "run", "dashboards/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
