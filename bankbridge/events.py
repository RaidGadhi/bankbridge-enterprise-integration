"""Optional Kafka/IBM Event Streams publisher for outbox completion events.

Event publishing has at-least-once semantics, not exactly-once Kafka-to-DB delivery.
Consumers must deduplicate by transfer_id and event_type.
"""
import json
import logging
import os
import time
from sqlalchemy import select
from .db import Outbox, make_engine, session_factory, utcnow
from .settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("bankbridge-events")
FINAL_EVENTS = ("payment.completed", "payment.rejected")


def make_producer():
    try:
        from kafka import KafkaProducer
    except ImportError as exc:
        raise RuntimeError("Install the optional 'events' extra: pip install '.[events]'") from exc
    hosts = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "").strip()
    if not hosts:
        raise RuntimeError("KAFKA_BOOTSTRAP_SERVERS is required for event publication")
    protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "SASL_SSL")
    options = dict(bootstrap_servers=[s.strip() for s in hosts.split(",") if s.strip()],
                   security_protocol=protocol, acks="all", retries=3,
                   key_serializer=lambda s: s.encode("utf-8"),
                   value_serializer=lambda s: s.encode("utf-8"))
    if protocol.startswith("SASL_"):
        options.update(sasl_mechanism=os.environ.get("KAFKA_SASL_MECHANISM", "PLAIN"),
                       sasl_plain_username=os.environ.get("KAFKA_USERNAME", "token"),
                       sasl_plain_password=os.environ.get("KAFKA_PASSWORD", ""))
    return KafkaProducer(**options)


def publish_final_once(Session, producer, topic: str) -> bool:
    with Session() as db:
        row = db.scalar(select(Outbox)
                        .where(Outbox.published_at.is_(None), Outbox.event_type.in_(FINAL_EVENTS))
                        .order_by(Outbox.id).limit(1))
        if row is None:
            return False
        # Kafka publish fully acknowledged before changing outbox state.
        future = producer.send(topic, key=row.aggregate_id, value=row.payload)
        future.get(timeout=20)
        row.published_at = utcnow()
        db.commit()
        LOG.info("published final event id=%s type=%s", row.id, row.event_type)
        return True


def main():
    settings = Settings()
    producer = make_producer()
    Session = session_factory(make_engine(settings.database_url))
    topic = os.environ.get("KAFKA_TOPIC", "bankbridge.payments.v1")
    while True:
        try:
            work = publish_final_once(Session, producer, topic)
            if not work:
                time.sleep(max(settings.poll_interval, 1))
        except Exception:
            LOG.exception("Kafka publish failed; outbox remains pending for retry")
            time.sleep(5)


if __name__ == "__main__":
    main()
