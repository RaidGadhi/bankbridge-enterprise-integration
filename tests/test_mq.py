from dataclasses import replace
from unittest.mock import patch
import requests
import pytest
from bankbridge.mq import publish_message, MQPublishError
from bankbridge.settings import Settings


def test_mq_publish_uses_persistent_message_and_csrf():
    cfg = replace(Settings(), mq_url="https://mq:9443", mq_password="not-real", mq_tls_verify=True)
    with patch("bankbridge.mq.requests.post") as post:
        post.return_value.status_code = 201
        publish_message('{"transfer_id":"test"}', cfg)
        _, kwargs = post.call_args
        assert "/ibmmq/rest/v3/messaging/qmgr/QM1/queue/DEV.QUEUE.1/message" in post.call_args.args[0]
        assert kwargs["headers"]["ibm-mq-md-persistence"] == "persistent"
        assert kwargs["headers"]["ibm-mq-rest-csrf-token"]
        assert kwargs["verify"] is True


def test_mq_publish_fails_closed():
    cfg = Settings()
    with patch("bankbridge.mq.requests.post", side_effect=requests.ConnectionError("unreachable")):
        with pytest.raises(MQPublishError):
            publish_message("{}", cfg)


def test_mq_publisher_skips_unpublished_completion_and_dispatches_next_request(test_context):
    """Avoid head-of-line blocking after first payment completes in MQ profile."""
    from decimal import Decimal
    from sqlalchemy import select
    from bankbridge.db import Outbox
    from bankbridge.domain import submit_transfer, process_transfer
    from bankbridge.worker import do_mq_once
    _, app = test_context
    with app.state.Session() as db:
        t1, _ = submit_transfer(db, source_id="DEMO-100", destination_id="DEMO-200",
                                amount=Decimal("1.00"), currency="SAR", key="mq-outbox-test-001")
    with patch('bankbridge.worker.publish_message') as pub:
        assert do_mq_once(app.state.Session, Settings()) is True
        with app.state.Session() as db:
            process_transfer(db, t1.transfer_id)
            t2, _ = submit_transfer(db, source_id="DEMO-100", destination_id="DEMO-200",
                                    amount=Decimal("2.00"), currency="SAR", key="mq-outbox-test-002")
        assert do_mq_once(app.state.Session, Settings()) is True
        assert pub.call_count == 2
    with app.state.Session() as db:
        completed = db.scalar(select(Outbox).where(Outbox.event_type == 'payment.completed'))
        assert completed.published_at is None  # awaiting Kafka producer; never falsely marked as sent


def test_mq_failure_keeps_outbox_unpublished(test_context):
    from decimal import Decimal
    from sqlalchemy import select
    from bankbridge.db import Outbox
    from bankbridge.domain import submit_transfer
    from bankbridge.worker import do_mq_once
    _, app = test_context
    with app.state.Session() as db:
        submit_transfer(db, source_id="DEMO-100", destination_id="DEMO-200",
                        amount=Decimal("1.00"), currency="SAR", key="mq-outbox-fail-001")
    with patch('bankbridge.worker.publish_message', side_effect=MQPublishError('network failure')):
        with pytest.raises(MQPublishError):
            do_mq_once(app.state.Session, Settings())
    with app.state.Session() as db:
        requested = db.scalar(select(Outbox).where(Outbox.event_type == 'payment.requested'))
        assert requested.published_at is None
