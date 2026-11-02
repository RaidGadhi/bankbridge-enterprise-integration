# Verification log and acceptance criteria

**Build snapshot:** 2026-11-02. This file separates observed results from future requirements.

## Performed in the authoring environment

* Live HTTP end-to-end smoke check using Uvicorn + SQLite: `GET /health/ready` returned HTTP 200, `POST /v1/transfers` returned HTTP 202, internal processing returned `COMPLETED`, repeated processing returned `already_processed: true`, source balance changed 10000.00 → 9987.66 and destination changed 2500.00 → 2512.34 — PASS. (Manual internal-API processing, not Docker worker or IBM MQ.)
* Python source compiled using `python -m compileall -q bankbridge` — PASS.
* `PYTHONPATH=. pytest -q` — **13 automated Python tests passed**.
* All `*.yaml` files parsed successfully with PyYAML — PASS.

Automated tests cover:

- Health and authentication enforcement
- Synthetic seeded account balances
- Transfer POST returning `PENDING`
- Completion changes both balances and writes two ledger entries
- Repeat internal processing does not apply the transaction twice
- Repeated `Idempotency-Key` returns the same transfer
- Changing the request under the same key returns HTTP 409
- Insufficient funds rejects without ledger changes
- Invalid amount, missing key, same account, missing account
- Local worker processes outbox
- IBM MQ REST publisher sends persistent messages with CSRF header (mocked)
- Publish transport errors fail closed (mocked)
- Kafka event-publish success/failure and outbox acknowledgement (mocked)

## Not performed here

- A Docker Compose build or live PostgreSQL transaction test (no Docker Engine present)
- An IBM MQ server/client handshake and real JMS transaction (no MQ runtime available)
- Maven-based Java compilation (Maven not present here)
- IBM ACE Toolkit compilation into a deployable BAR
- IBM API Connect import and policy execution
- IBM Event Streams / Kafka broker connectivity
- Any OpenShift installation, pod, Route or actual failover test
- Distributed concurrency, chaos tests, throughput benchmarking, backup restore, or security scanning

## Minimum additional acceptance gates before presenting as a fully demonstrated IBM integration

1. Run `bash scripts/demo.sh`; capture the successful real HTTP smoke test.
2. Run `bash scripts/ibm-demo.sh`; verify MQ publisher and JMS consumer logs.
3. Kill/restart the JMS consumer mid-processing and verify one pair of ledger entries.
4. Import `deploy/apiconnect/bankbridge-openapi.yaml` into API Connect trial and show an authenticated request.
5. Build and deploy a *real* ACE message flow in the Toolkit; replace this repo's ESQL example with project exports / a shareable BAR build procedure (not IBM binaries).
6. Configure Kafka/IBM Event Streams and validate `payment.completed` delivery.
7. Build/push the image, create secrets and deploy the OpenShift manifests; show readiness and liveness probes.
8. Publish screenshots/logs and a short demo without secrets or employer data.

**CV honesty rule:** You may say you implemented the tested core now, but do not claim production CP4I, ACE integration, real MQ event processing, or OpenShift deployment until the corresponding test gate has passed.
