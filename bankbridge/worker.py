"""Outbox workers. Local path is fully runnable without IBM entitlements.

Local mode simulates asynchronous dispatch with the DB outbox. IBM mode puts only
request events to MQ; external JMS worker consumes and calls internal HTTP API.
"""
import argparse
import json
import logging
import time
from sqlalchemy import select
from .db import Outbox, Transfer, utcnow, make_engine, session_factory
from .domain import process_transfer
from .mq import publish_message, MQPublishError
from .settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bankbridge-worker")


def do_local_once(Session) -> bool:
    """A synchronous development-mode dispatcher. Single worker only.

    The outbox row remains pending until the DB ledger change commits. Never run
    multiple local workers; use IBM MQ transactional consumption for concurrency.
    """
    with Session() as session:
        row = session.scalar(select(Outbox).where(Outbox.published_at.is_(None))
                             .order_by(Outbox.id).limit(1))
        if row is None:
            return False
        if row.event_type == "payment.requested":
            try:
                t, duplicate = process_transfer(session, row.aggregate_id)
                logger.info("local transfer=%s status=%s duplicate=%s", t.transfer_id, t.status, duplicate)
            except Exception:
                session.rollback()
                raise
        row = session.get(Outbox, row.id)
        row.published_at = utcnow()
        session.commit()
        return True


def do_mq_once(Session, settings: Settings) -> bool:
    with Session() as session:
        # Single MQ outbox publisher instance in this proof of concept.
        row = session.scalar(select(Outbox).where(Outbox.published_at.is_(None),
                                       Outbox.event_type == "payment.requested")
                             .order_by(Outbox.id).limit(1))
        if row is None:
            return False
        # Only requested events are queued to the payment worker. Completed and
        # rejected events are durable in the outbox but are not yet Kafka-published.
        if row.event_type == "payment.requested":
            publish_message(row.payload, settings)
            logger.info("published IBM MQ outbox=%s aggregate=%s", row.id, row.aggregate_id)
        else:
            logger.info("retained completion event in DB outbox id=%s; Kafka publisher not enabled", row.id)
            return False  # Prevent falsely marking final events as delivered.
        row.published_at = utcnow()
        session.commit()
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("local", "mq"), help="local demo or MQ outbox publisher")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    engine = make_engine(settings.database_url)
    Session = session_factory(engine)
    logger.info("starting mode=%s", args.mode)
    while True:
        try:
            did_work = do_local_once(Session) if args.mode == "local" else do_mq_once(Session, settings)
        except Exception:
            logger.exception("worker failed; will retry")
            did_work = False
        if args.once:
            break
        if not did_work:
            time.sleep(settings.poll_interval if args.mode == "local" else max(2, settings.poll_interval))


if __name__ == "__main__":
    main()
