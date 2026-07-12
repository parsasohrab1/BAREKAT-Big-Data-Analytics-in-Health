FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dashboards/ ./dashboards/
COPY data/ ./data/

ENV DATA_DIR=/app/data/raw
ENV MODELS_DIR=/app/data/models
ENV PYTHONPATH=/app
EXPOSE 8501

CMD ["streamlit", "run", "dashboards/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
