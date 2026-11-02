from bankbridge.events import publish_final_once
from bankbridge.domain import submit_transfer, process_transfer
from decimal import Decimal
from sqlalchemy import select
from bankbridge.db import Outbox


class Ack:
    def get(self, timeout):
        return {"ack": True}


class Publisher:
    def __init__(self, fail=False):
        self.sent = []
        self.fail = fail

    def send(self, topic, key, value):
        self.sent.append((topic, key, value))
        if self.fail:
            class Broken:
                def get(self, timeout):
                    raise OSError("Kafka unreachable")
            return Broken()
        return Ack()


def test_events_published_only_after_ack(test_context):
    client, app = test_context
    with app.state.Session() as db:
        t, _ = submit_transfer(db, source_id="DEMO-100", destination_id="DEMO-200",
                               amount=Decimal("15.00"), currency="SAR", key="event-test-00001")
        process_transfer(db, t.transfer_id)
    failed = Publisher(fail=True)
    try:
        publish_final_once(app.state.Session, failed, "payment-events")
        assert False, "expected failure"
    except OSError:
        pass
    with app.state.Session() as db:
        row = db.scalar(select(Outbox).where(Outbox.event_type == "payment.completed"))
        assert row.published_at is None
    good = Publisher()
    assert publish_final_once(app.state.Session, good, "payment-events")
    assert good.sent[0][0] == "payment-events"
    assert good.sent[0][1] == t.transfer_id
    assert publish_final_once(app.state.Session, good, "payment-events") is False
