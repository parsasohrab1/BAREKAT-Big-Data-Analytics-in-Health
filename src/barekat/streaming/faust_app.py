"""Faust stream processor for HL7/FHIR events."""

from __future__ import annotations

import faust

from barekat.config.settings import get_settings
from barekat.services.alerts import persist_streaming_alert
from barekat.streaming.processors import detect_alerts
from barekat.streaming.redis_bridge import publish_live_alert

settings = get_settings()

app = faust.App(
    "barekat-stream",
    broker=f"kafka://{settings.kafka_bootstrap_servers}",
    store="memory://",
    version=1,
)


class HealthEventRecord(faust.Record, serializer="json"):
    event_id: str
    source: str
    event_type: str
    patient_id: str
    admission_id: str = ""
    timestamp: str = ""
    payload: dict = {}


class AlertRecord(faust.Record, serializer="json"):
    alert_id: str
    patient_id: str
    admission_id: str = ""
    alert_type: str
    severity: str
    message: str
    risk_score: float
    source_event_id: str = ""
    source: str = ""
    timestamp: str = ""


events_topic = app.topic(settings.kafka_topic_events_raw, value_type=HealthEventRecord)
alerts_topic = app.topic(settings.kafka_topic_alerts, value_type=AlertRecord)


@app.agent(events_topic)
async def process_health_events(events):
    """Consume normalized events, detect alerts, fan-out to Kafka + Redis + PostgreSQL."""
    async for event in events:
        event_dict = event.asdict()
        for alert in detect_alerts(event_dict):
            alert_record = AlertRecord(**alert)
            await alerts_topic.send(key=alert["alert_id"], value=alert_record)
            try:
                publish_live_alert(alert)
            except Exception as exc:
                print(f"Redis publish failed: {exc}")
            try:
                persist_streaming_alert(alert)
            except Exception as exc:
                print(f"DB persist failed: {exc}")


if __name__ == "__main__":
    app.main()
