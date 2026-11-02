"""Relational database model and session lifecycle."""
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Numeric, ForeignKey,
    UniqueConstraint, CheckConstraint, Index, Text,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, relationship
from sqlalchemy.pool import StaticPool


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"
    account_id = Column(String(36), primary_key=True)
    owner = Column(String(120), nullable=False)
    balance = Column(Numeric(18, 2, asdecimal=True), nullable=False)
    currency = Column(String(3), nullable=False, default="SAR")
    __table_args__ = (CheckConstraint("balance >= 0", name="nonnegative_balance"),)


class Transfer(Base):
    __tablename__ = "transfers"
    transfer_id = Column(String(36), primary_key=True)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    request_hash = Column(String(64), nullable=False)
    source_id = Column(String(36), ForeignKey("accounts.account_id"), nullable=False)
    destination_id = Column(String(36), ForeignKey("accounts.account_id"), nullable=False)
    amount = Column(Numeric(18, 2, asdecimal=True), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    rejection_reason = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (
        CheckConstraint("amount > 0", name="positive_transfer"),
        CheckConstraint("source_id != destination_id", name="distinct_accounts"),
        Index("idx_transfers_status", "status"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    transfer_id = Column(String(36), ForeignKey("transfers.transfer_id"), nullable=False)
    account_id = Column(String(36), ForeignKey("accounts.account_id"), nullable=False)
    change = Column(Numeric(18, 2, asdecimal=True), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    __table_args__ = (UniqueConstraint("transfer_id", "account_id", name="one_entry_per_account_transfer"),)


class Outbox(Base):
    __tablename__ = "outbox"
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(100), nullable=False)
    aggregate_id = Column(String(36), nullable=False)
    payload = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    published_at = Column(DateTime(timezone=True), nullable=True)
    __table_args__ = (Index("idx_outbox_unpublished", "published_at", "id"),)


def make_engine(url):
    kwargs = {"future": True, "pool_pre_ping": True}
    if url == "sqlite://" or url == "sqlite:///:memory:":
        kwargs["connect_args"] = {"check_same_thread": False}
        kwargs["poolclass"] = StaticPool
    elif url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def seed_demo(session):
    """Seed clearly fictional accounts; idempotent and disabled by default in live deployments."""
    fixtures = [
        ("DEMO-100", "Demo Customer Alice", Decimal("10000.00")),
        ("DEMO-200", "Demo Customer Bob", Decimal("2500.00")),
        ("DEMO-300", "Demo Customer Charlie", Decimal("100.00")),
    ]
    for account_id, owner, balance in fixtures:
        if session.get(Account, account_id) is None:
            session.add(Account(account_id=account_id, owner=owner, balance=balance, currency="SAR"))
    session.commit()
