# Architecture decision records

## ADR-001 — Transactional outbox rather than direct publish from the API
**Decision:** Persist transfer + event in one DB transaction, then publish asynchronously.
**Reason:** A direct network publish after debit could lose notification if the API crashes; publishing before commit could trigger work for a transaction that later rolls back.
**Trade-off:** The outbox must be polled and monitored; publication is at-least-once.

## ADR-002 — Idempotency at both API and ledger boundaries
**Decision:** Unique request key + immutable request fingerprint; terminal transfer state checked inside PostgreSQL row lock.
**Reason:** HTTP retries and MQ redelivery are expected in distributed systems.
**Trade-off:** Clients must supply stable, unique keys. Real systems need retention policies.

## ADR-003 — Transacted JMS consumer instead of destructive MQ REST reads
**Decision:** REST endpoint only for persistent IBM MQ PUT; JMS transacted session for GET/ACK.
**Reason:** Destructive REST GET followed by database processing may lose the message on process crash.
**Trade-off:** A small Java runtime is needed. MQ and DB commit cannot be atomic across the HTTP boundary, so redelivery+idempotency are mandatory.

## ADR-004 — Decimal money and double-entry records
**Decision:** PostgreSQL NUMERIC(18,2) and Python Decimal, two opposing postings for each successful transfer.
**Reason:** Floating-point precision and single mutable balances make accounting auditability weaker.
**Trade-off:** This is still a toy ledger; no authorization holds, dispute handling, reconciliation, double-spend across external rails, or regulatory controls.

## ADR-005 — Separate IBM trial workloads from verified open source core
**Decision:** A local Docker development path, plus independently optional IBM MQ, Kafka, ACE and API Connect paths.
**Reason:** IBM product evaluation licenses and runtimes have real access restrictions; GitHub readers must be able to reproduce the main behavior without those credentials.
**Trade-off:** Not one full deployed CP4I environment. Documentation intentionally identifies unverified integration seams.

## ADR-006 — Kafka terminal events with acknowledgements
**Decision:** Publish JSON terminal event with `transfer_id` as Kafka record key; update outbox only after ack.
**Reason:** A durable event handoff to downstream services enables eventual-consistency style integrations.
**Trade-off:** Kafka and DB are not one atomic transaction. Duplicates possible; dedupe downstream by `(event_type, transfer_id)`.
