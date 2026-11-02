# Failure drills (synthetic test data only)

## Verified by automated tests

1. Submit 100.00 SAR -> state `PENDING` -> process -> `COMPLETED`.
2. Process that UUID again -> `already_processed: true` -> balances unchanged.
3. Replay original `Idempotency-Key` -> same UUID; change amount under same key -> HTTP 409.
4. Transfer 101.00 SAR from DEMO-300 (balance 100.00) -> `REJECTED`; ledger empty.
5. Simulate failed MQ REST publication through a mocked network exception -> publisher reports error rather than marking success.
6. Simulate failed Kafka publication through a mocked Future -> completion event remains unpublished.

## Run these after setting up live IBM MQ

1. Stop `mq-consumer`; post a new transfer. Confirm `PENDING` while the requested message is queued.
2. Start `mq-consumer`. Confirm `COMPLETED`; inspect one negative and one positive ledger entry.
3. Restart MQ consumer during processing, use transfer UUID to query ledger and count postings; observe whether redelivery occurred. A simple restart is **not** proof that a failure occurred at the commit boundary.
4. Stop MQ before publishing; confirm outbox remains pending, start MQ and confirm eventual processing.
5. Send malformed message only in the isolated dev environment, confirm poison routing or rollback behavior.
6. For a stronger crash-boundary test, add deterministic fault injection after PostgreSQL commit and before JMS commit; then assert exactly two ledger entries despite MQ redelivery.

## Evidence checklist

Capture HTTP request/response, returned UUID, account before/after balances, ledger, MQ console queue depths, sanitized JVM log, outbox status and clear timestamps. Document exact environment/version and test limitations. No secrets or employer data in screenshots.
