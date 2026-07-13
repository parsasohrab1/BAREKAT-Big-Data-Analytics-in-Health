"""Kafka producer for streaming health events."""

from __future__ import annotations

import json
from typing import Any

from confluent_kafka import Consumer, Producer

from barekat.config.settings import get_settings


class EventProducer:
    def __init__(self) -> None:
        settings = get_settings()
        self.producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
        self.topics = {
            "admissions": settings.kafka_topic_admissions,
            "lab_results": settings.kafka_topic_lab_results,
            "alerts": settings.kafka_topic_alerts,
            "events_raw": settings.kafka_topic_events_raw,
            "hl7": settings.kafka_topic_hl7,
            "fhir": settings.kafka_topic_fhir,
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

    def publish_raw_event(self, event: dict[str, Any]) -> None:
        self.publish("events_raw", event.get("event_id", "event"), event)

    def publish_hl7(self, event: dict[str, Any]) -> None:
        self.publish("hl7", event.get("event_id", "hl7"), event)

    def publish_fhir(self, event: dict[str, Any]) -> None:
        self.publish("fhir", event.get("event_id", "fhir"), event)


class EventConsumer:
    def __init__(self, group_id: str = "barekat-api-alerts") -> None:
        settings = get_settings()
        self.consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "latest",
        })

    def subscribe(self, topics: list[str]) -> None:
        self.consumer.subscribe(topics)

    def poll(self, timeout: float = 1.0):
        return self.consumer.poll(timeout)

    def close(self) -> None:
        self.consumer.close()
