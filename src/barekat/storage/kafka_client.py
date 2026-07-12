"""Kafka producer for streaming health events."""

import json
from typing import Any

from confluent_kafka import Producer

from barekat.config.settings import get_settings


class EventProducer:
    def __init__(self) -> None:
        settings = get_settings()
        self.producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
        self.topics = {
            "admissions": settings.kafka_topic_admissions,
            "lab_results": settings.kafka_topic_lab_results,
            "alerts": settings.kafka_topic_alerts,
        }

    def _delivery_callback(self, err, msg) -> None:
        if err:
            print(f"Kafka delivery failed: {err}")

    def publish(self, topic_key: str, key: str, value: dict[str, Any]) -> None:
        topic = self.topics.get(topic_key, topic_key)
        self.producer.produce(
            topic,
            key=key.encode("utf-8"),
            value=json.dumps(value, default=str).encode("utf-8"),
            callback=self._delivery_callback,
        )
        self.producer.flush(timeout=5)

    def publish_admission_event(self, admission_id: str, data: dict[str, Any]) -> None:
        self.publish("admissions", admission_id, data)

    def publish_alert(self, alert_id: str, data: dict[str, Any]) -> None:
        self.publish("alerts", alert_id, data)
