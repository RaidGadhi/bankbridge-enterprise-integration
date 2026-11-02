"""HTTP boundaries for demo banking API and controlled internal worker operations."""
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated
import hmac
import os
import re
from fastapi import FastAPI, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from .db import Base, Account, Transfer, LedgerEntry, Outbox, make_engine, session_factory, seed_demo
from .domain import DomainError, submit_transfer, process_transfer, transfer_to_dict
from .settings import Settings


class TransferRequest(BaseModel):
    from_account: str = Field(min_length=1, max_length=36)
    to_account: str = Field(min_length=1, max_length=36)
    amount: Decimal = Field(gt=0, le=Decimal("999999999.99"), max_digits=11, decimal_places=2)
    currency: str = "SAR"

    @field_validator("amount")
    @classmethod
    def cents_only(cls, val):
        if not val.is_finite() or val.as_tuple().exponent < -2:
            raise ValueError("Amount must be a finite number with at most two decimal places")
        return val


def create_app(settings: Settings | None = None, *, db_url: str | None = None):
    settings = settings or Settings()
    engine = make_engine(db_url or settings.database_url)
    Session = session_factory(engine)

    @asynccontextmanager
    async def lifespan(app):
        # Demo schema bootstrap; migrations required for production.
        Base.metadata.create_all(engine)
        if settings.allow_demo_seed:
            with Session() as session:
                seed_demo(session)
        yield
        engine.dispose()

    app = FastAPI(title="BankBridge Enterprise Integration Demo", version="1.0.0",
                  description="Simulated accounts only. No actual money movement.", lifespan=lifespan)
    app.state.Session = Session
    app.state.engine = engine
    app.state.settings = settings

    def get_db():
        with Session() as db:
            try:
                yield db
            finally:
                db.rollback()

    def api_auth(x_api_key: Annotated[str | None, Header()] = None):
        if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
            raise HTTPException(status_code=401, detail="Invalid API key")

    def internal_auth(x_internal_token: Annotated[str | None, Header()] = None):
        if not x_internal_token or not hmac.compare_digest(x_internal_token, settings.internal_token):
            raise HTTPException(status_code=401, detail="Invalid internal token")

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready(db=Depends(get_db)):
        try:
            db.execute(select(Account.account_id).limit(1)).first()
            return {"status": "ready"}
        except Exception:
            raise HTTPException(status_code=503, detail="Database unavailable")

    @app.get("/v1/accounts/{account_id}", dependencies=[Depends(api_auth)], tags=["demo banking"])
    def get_account(account_id: str, db=Depends(get_db)):
        a = db.get(Account, account_id)
        if not a:
            raise HTTPException(status_code=404, detail="Account not found")
        return {"account_id": a.account_id, "owner": a.owner, "balance": f"{a.balance:.2f}", "currency": a.currency}

    @app.post("/v1/transfers", status_code=202, dependencies=[Depends(api_auth)], tags=["demo banking"])
    def post_transfer(payload: TransferRequest, response: Response,
                      idempotency_key: Annotated[str | None, Header()] = None,
                      db=Depends(get_db)):
        if not idempotency_key or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
            raise HTTPException(status_code=422, detail="Idempotency-Key must be 8-128 URL-safe characters")
        try:
            t, duplicate = submit_transfer(
                db, source_id=payload.from_account, destination_id=payload.to_account,
                amount=payload.amount, currency=payload.currency, key=idempotency_key)
            response.headers["X-Idempotent-Replay"] = str(duplicate).lower()
            return transfer_to_dict(t)
        except DomainError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.message)

    @app.get("/v1/transfers/{transfer_id}", dependencies=[Depends(api_auth)], tags=["demo banking"])
    def get_transfer(transfer_id: str, db=Depends(get_db)):
        t = db.get(Transfer, transfer_id)
        if not t:
            raise HTTPException(status_code=404, detail="Transfer not found")
        return transfer_to_dict(t)

    @app.post("/internal/process/{transfer_id}", dependencies=[Depends(internal_auth)], tags=["internal"])
    def internal_process(transfer_id: str, db=Depends(get_db)):
        try:
            transfer, duplicate = process_transfer(db, transfer_id)
            return {**transfer_to_dict(transfer), "already_processed": duplicate}
        except DomainError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.message)

    @app.get("/internal/outbox", dependencies=[Depends(internal_auth)], tags=["internal"])
    def inspect_outbox(db=Depends(get_db)):
        rows = db.scalars(select(Outbox).order_by(Outbox.id).limit(200)).all()
        return [{"id": r.id, "event_type": r.event_type, "aggregate_id": r.aggregate_id,
                 "published": r.published_at is not None} for r in rows]

    @app.get("/internal/ledger/{transfer_id}", dependencies=[Depends(internal_auth)], tags=["internal"])
    def ledger(transfer_id: str, db=Depends(get_db)):
        rows = db.scalars(select(LedgerEntry).where(LedgerEntry.transfer_id == transfer_id)).all()
        return [{"account_id": r.account_id, "change": f"{r.change:.2f}"} for r in rows]

    return app


app = create_app()
