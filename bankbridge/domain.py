"""Financial correctness primitives. Synthetic money only; not a banking product."""
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
import json
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import Account, Transfer, LedgerEntry, Outbox, utcnow


class TransferStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class DomainError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message, self.status = message, status
        super().__init__(message)


def fingerprint(source_id: str, destination_id: str, amount: Decimal, currency: str) -> str:
    payload = {"from": source_id, "to": destination_id, "amount": f"{amount:.2f}", "currency": currency}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def transfer_to_dict(t: Transfer) -> dict:
    return {"transfer_id": t.transfer_id, "from_account": t.source_id,
            "to_account": t.destination_id, "amount": f"{t.amount:.2f}",
            "currency": t.currency, "status": t.status, "rejection_reason": t.rejection_reason,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "processed_at": t.processed_at.isoformat() if t.processed_at else None}


def enqueue_event(session, name: str, transfer: Transfer):
    payload = {"schema_version": 1, "event_type": name, "transfer_id": transfer.transfer_id,
               "from_account": transfer.source_id, "to_account": transfer.destination_id,
               "amount": f"{transfer.amount:.2f}", "currency": transfer.currency,
               "status": transfer.status}
    session.add(Outbox(event_type=name, aggregate_id=transfer.transfer_id,
                       payload=json.dumps(payload, separators=(",", ":"))))


def submit_transfer(session, *, source_id: str, destination_id: str, amount: Decimal,
                    currency: str, key: str) -> tuple[Transfer, bool]:
    digest = fingerprint(source_id, destination_id, amount, currency)
    existing = session.scalar(select(Transfer).where(Transfer.idempotency_key == key))
    if existing:
        if existing.request_hash != digest:
            raise DomainError("Idempotency-Key was already used with a different request", 409)
        return existing, True
    if source_id == destination_id:
        raise DomainError("Source and destination must differ")
    if currency != "SAR":
        raise DomainError("Only SAR is supported by the demo")
    for account_id in (source_id, destination_id):
        account = session.get(Account, account_id)
        if account is None:
            raise DomainError(f"Account not found: {account_id}", 404)
        if account.currency != currency:
            raise DomainError("Account currency mismatch")
    transfer = Transfer(transfer_id=str(uuid.uuid4()), idempotency_key=key,
                        request_hash=digest, source_id=source_id,
                        destination_id=destination_id, amount=amount,
                        currency=currency, status=TransferStatus.PENDING.value)
    session.add(transfer)
    enqueue_event(session, "payment.requested", transfer)
    try:
        session.commit()
    except IntegrityError:
        # Concurrent identical submissions: unique constraint is the authority.
        session.rollback()
        existing = session.scalar(select(Transfer).where(Transfer.idempotency_key == key))
        if existing and existing.request_hash == digest:
            return existing, True
        if existing:
            raise DomainError("Idempotency-Key was already used with a different request", 409)
        raise
    return transfer, False


def process_transfer(session, transfer_id: str) -> tuple[Transfer, bool]:
    """A single DB transaction enforces exactly-once ledger effects (not exactly-once delivery).

    Postgres row locks serialize concurrent processing; account locks are ordered to avoid
    deadlocks. Redelivery is safe after a consumer crash between DB commit and MQ ACK.
    """
    transfer = session.scalar(select(Transfer).where(Transfer.transfer_id == transfer_id).with_for_update())
    if transfer is None:
        raise DomainError("Transfer not found", 404)
    if transfer.status != TransferStatus.PENDING.value:
        return transfer, True
    rows = session.scalars(
        select(Account).where(Account.account_id.in_([transfer.source_id, transfer.destination_id]))
        .order_by(Account.account_id).with_for_update()
    ).all()
    by_id = {a.account_id: a for a in rows}
    source = by_id[transfer.source_id]
    destination = by_id[transfer.destination_id]
    if source.balance < transfer.amount:
        transfer.status = TransferStatus.REJECTED.value
        transfer.rejection_reason = "INSUFFICIENT_FUNDS"
        enqueue_event(session, "payment.rejected", transfer)
    else:
        source.balance -= transfer.amount
        destination.balance += transfer.amount
        session.add(LedgerEntry(transfer_id=transfer.transfer_id, account_id=source.account_id,
                                change=-transfer.amount))
        session.add(LedgerEntry(transfer_id=transfer.transfer_id, account_id=destination.account_id,
                                change=transfer.amount))
        transfer.status = TransferStatus.COMPLETED.value
        enqueue_event(session, "payment.completed", transfer)
    transfer.processed_at = utcnow()
    session.commit()
    return transfer, False
