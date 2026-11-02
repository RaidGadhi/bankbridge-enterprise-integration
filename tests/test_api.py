import uuid
from decimal import Decimal
from sqlalchemy import select, func
from bankbridge.db import Account, Transfer, LedgerEntry, Outbox
from bankbridge.worker import do_local_once


def request_body(amount="100.00", from_account="DEMO-100", to_account="DEMO-200"):
    return {"from_account": from_account, "to_account": to_account, "amount": amount, "currency": "SAR"}


def submit(client, auth, key, body=None):
    return client.post("/v1/transfers", headers={**auth, "Idempotency-Key": key},
                       json=body or request_body())


def test_health_auth_and_initial_balances(test_context, auth, internal):
    client, _ = test_context
    assert client.get("/health/ready").status_code == 200
    assert client.get("/v1/accounts/DEMO-100").status_code == 401
    assert client.post("/internal/process/anything").status_code == 401
    assert client.get("/v1/accounts/DEMO-100", headers=auth).json()["balance"] == "10000.00"


def test_complete_atomic_and_exactly_once_effect(test_context, auth, internal):
    client, app = test_context
    key = "payment-test-0001"
    submitted = submit(client, auth, key)
    assert submitted.status_code == 202
    tid = submitted.json()["transfer_id"]
    assert submitted.json()["status"] == "PENDING"
    first = client.post(f"/internal/process/{tid}", headers=internal)
    assert first.status_code == 200
    assert first.json()["status"] == "COMPLETED"
    second = client.post(f"/internal/process/{tid}", headers=internal)
    assert second.json()["already_processed"] is True
    again = submit(client, auth, key)
    assert again.status_code == 202
    assert again.headers["X-Idempotent-Replay"] == "true"
    assert again.json()["transfer_id"] == tid
    assert client.get("/v1/accounts/DEMO-100", headers=auth).json()["balance"] == "9900.00"
    assert client.get("/v1/accounts/DEMO-200", headers=auth).json()["balance"] == "2600.00"
    assert sorted(x["change"] for x in client.get(f"/internal/ledger/{tid}", headers=internal).json()) == ["-100.00", "100.00"]
    with app.state.Session() as s:
        assert s.scalar(select(func.count()).select_from(LedgerEntry)) == 2
        assert s.scalar(select(func.count()).select_from(Transfer)) == 1


def test_rejected_insufficient_funds_and_no_entries(test_context, auth, internal):
    client, app = test_context
    resp = submit(client, auth, "payment-test-0002", request_body("101.00", from_account="DEMO-300"))
    assert resp.status_code == 202
    tid = resp.json()["transfer_id"]
    response = client.post(f"/internal/process/{tid}", headers=internal)
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "INSUFFICIENT_FUNDS"
    assert client.get(f"/internal/ledger/{tid}", headers=internal).json() == []
    assert client.get("/v1/accounts/DEMO-300", headers=auth).json()["balance"] == "100.00"


def test_idempotency_key_conflict(test_context, auth):
    client, _ = test_context
    assert submit(client, auth, "payment-test-0003").status_code == 202
    conflict = submit(client, auth, "payment-test-0003", request_body("200.00"))
    assert conflict.status_code == 409


def test_invalid_money_and_request(test_context, auth):
    client, _ = test_context
    for amount in ["0.00", "-1.00", "1.001", "NaN", "1000000000.00"]:
        assert submit(client, auth, str(uuid.uuid4()), request_body(amount)).status_code == 422
    assert submit(client, auth, "a-key-value-abc", request_body(from_account="DEMO-100", to_account="DEMO-100")).status_code == 400
    assert submit(client, auth, "other-key-001", request_body(from_account="NOT-FOUND")).status_code == 404
    assert client.post("/v1/transfers", headers=auth, json=request_body()).status_code == 422


def test_local_worker_processes_event_and_preserves_outbox(test_context, auth, internal):
    client, app = test_context
    tid = submit(client, auth, "payment-test-0004").json()["transfer_id"]
    assert do_local_once(app.state.Session) is True
    assert client.get(f"/v1/transfers/{tid}", headers=auth).json()["status"] == "COMPLETED"
    assert do_local_once(app.state.Session) is True  # completed event marked delivered in local mode
    assert do_local_once(app.state.Session) is False
    assert all(x["published"] for x in client.get("/internal/outbox", headers=internal).json())


def test_two_separate_transfers_deduct_correctly(test_context, auth, internal):
    client, _ = test_context
    a = submit(client, auth, "payment-test-0005", request_body("200.00")).json()["transfer_id"]
    b = submit(client, auth, "payment-test-0006", request_body("300.00")).json()["transfer_id"]
    client.post(f"/internal/process/{a}", headers=internal)
    client.post(f"/internal/process/{b}", headers=internal)
    assert client.get("/v1/accounts/DEMO-100", headers=auth).json()["balance"] == "9500.00"
    assert client.get("/v1/accounts/DEMO-200", headers=auth).json()["balance"] == "3000.00"
