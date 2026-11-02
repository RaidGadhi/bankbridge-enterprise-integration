# Architecture and integration responsibilities

## System boundary

This is **one synthetic payment ledger** accessed through a REST API. Three mutually exclusive or independent deployment paths are shown:

1. **Local path:** outbox table -> local dispatcher -> same database transaction processor (verified by Python tests).
2. **IBM MQ path:** outbox -> MQ REST persistent PUT -> IBM MQ queue -> JMS transacted GET -> internal HTTP API -> PostgreSQL transaction -> JMS commit (requires real IBM MQ integration testing).
3. **Kafka output:** terminal event in outbox -> Kafka `acks=all` publication -> outbox `published_at` update (requires Kafka integration testing).

These are not a substitute for a full CP4I architectural topology, IBM ACE compiled flow, API Connect gateway or full OpenShift cluster.

## Payment lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant User as Client
    participant API as Payment API
    participant DB as PostgreSQL
    participant MQ as IBM MQ (optional)
    participant JMS as JMS consumer
    User->>API: POST /v1/transfers + Idempotency-Key
    API->>DB: Insert PENDING transfer and requested outbox atomically
    API-->>User: 202 + transfer_id
    Note over DB,MQ: Local mode processes outbox directly; IBM mode sends persistent MQ message
    DB-->>MQ: Outbox publisher sends payment.requested
    MQ-->>JMS: Receive with transactional JMS session
    JMS->>API: POST /internal/process/{id}
    API->>DB: Row locks, debit+credit, ledger, terminal event, COMMIT
    API-->>JMS: COMPLETED / REJECTED
    JMS->>MQ: COMMIT MQ transaction
    Note over JMS,DB: If JMS crashes before commit, MQ redelivers. DB recognizes terminal status.
    User->>API: GET /v1/transfers/{id}
    API-->>User: terminal status
```

## Data entities

* `accounts(account_id PK, owner, balance NUMERIC(18,2), currency)`
* `transfers(transfer_id PK, idempotency_key UNIQUE, request_hash, source_id, destination_id, amount, status, created_at, processed_at)`
* `ledger_entries(id PK, transfer_id, account_id, change, posted_at)` with unique transfer/account pair
* `outbox(id PK, event_type, aggregate_id, payload, created_at, published_at)`

### Invariants

1. For every completed payment, one negative ledger posting and one positive ledger posting must sum to zero.
2. A completed payment cannot be applied twice; `status != PENDING` exits before balance changes.
3. Account balances must not become negative; insufficiency results in terminal `REJECTED`.
4. Reusing the same idempotency key with identical payload returns the original transfer; using a different payload gives HTTP 409.
5. Publishing a message can be retried, because DB effects are idempotent. **Message delivery remains at-least-once**, not exactly-once.
6. A Kafka completion event may also be delivered twice after ambiguous acknowledgement; downstream consumers need event-level deduplication.

## Account locking and concurrency

The PostgreSQL execution path locks a transfer row and locks both account rows in ascending ID order using `SELECT ... FOR UPDATE`. This prevents concurrent balances from racing and minimizes deadlock cycles. A transfer result and its outbox event are committed in the same transaction. SQLite is only for single-worker local exploration.

## MQ failure matrix

| Failure | Expected design | Limitation |
|---|---|---|
| MQ broker is unavailable before publish | Outbox remains unpublished and publisher retries | Requires operational alerting |
| MQ accepts PUT, HTTP response is lost | Outbox retries and MQ may contain duplicate | DB idempotency prevents duplicate ledger effect |
| JMS worker crashes before DB commit | JMS message is rolled back/redelivered | Verify in real IBM MQ |
| DB commit succeeds, JMS worker crashes before MQ commit | JMS message redelivered, terminal status makes processing a no-op | Verify in real IBM MQ |
| Validation-poison message | JMS sends to DEV.QUEUE.2 after configured delivery threshold | Validate developer queue existence and MQ permissions |
| PostgreSQL loses storage | Not solved by this reference | Needs actual backups, replicas and restore tests |

## High availability and disaster recovery

This design **does not claim HA**. Two OpenShift API replicas protect only the stateless API tier. To claim HA, test PostgreSQL replication/failover, MQ native HA or DR, Kafka partition replication, pod anti-affinity, egress, TLS, failover RTO/RPO, and restore drills. Those are explicit follow-on validations, not fabricated results.
