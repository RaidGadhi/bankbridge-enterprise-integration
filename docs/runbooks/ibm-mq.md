# Operator runbook — IBM MQ Developer (optional)

**Goal:** Replace the local database-only worker with a durable IBM MQ queue and a Java JMS transacted consumer. This demo needs an x86_64-capable host with Docker, image download connectivity, and acceptance of IBM's developer license. It is not a production MQ setup.

1. Execute `bash scripts/demo.sh` once. Confirm `SUCCESS: single debit + credit`.
2. Stop the local worker: `docker compose --profile local stop local-worker`.
3. Start the MQ profile: `bash scripts/ibm-demo.sh`. IBM MQ can take time to initialize on first boot.
4. Follow logs: `docker compose --profile ibm logs -f mq mq-dispatcher mq-consumer`.
5. Verify both the publisher and JMS connection are active before submitting a test: `bash scripts/smoke-test.sh`.
6. Verify the two entries in `GET /internal/ledger/{transfer_id}` via internal token, the account balances, and MQ consumer output.

Default MQ resources: QM1, `DEV.QUEUE.1` work queue, `DEV.QUEUE.2` poison queue, `DEV.QUEUE.3` available for optional ACE routing, channel `DEV.APP.SVRCONN`. See [IBM developer-config](https://github.com/ibm-messaging/mq-container/blob/master/docs/developer-config.md).

## Why two transport mechanisms?

* Outbox publisher uses IBM MQ HTTPS REST API with `ibm-mq-md-persistence: persistent` and a CSRF header.
* Java uses JMS with `Session.SESSION_TRANSACTED`. It calls the internal API and commits MQ only after a 2xx response. For transient HTTP errors or connection failure, it rolls back the JMS receive and retries.
* If HTTP succeeds but MQ commit fails, message is redelivered; database checks transfer terminal state and prevents duplicate debit.
* Malformed / permanently unprocessable messages eventually move to `DEV.QUEUE.2` in the *same MQ transaction*, after up to five delivery attempts. Do not forward sensitive payloads into demo poison queues.
* IBM MQ REST itself does not participate in the PostgreSQL transaction, so the outbox producer might publish duplicates following ambiguous delivery.

## Developer TLS warning

The MQ image can start with a self-signed mqweb certificate. `.env` example sets `MQ_TLS_VERIFY=false` for **localhost-only development**. Production must trust the actual CA and use nonadmin message credentials; JVM connections here use an unencrypted developer channel. Never expose port 1414 or 9443 to the Internet.

## Troubleshooting

**MQ REST 401 / 403:** Check `MQ_ADMIN_PASSWORD`, the mqweb console login and MQ authority. Confirm the 9.3.5.1 image supports the selected password settings.

**MQ REST 404:** Check queue manager `QM1`, queue name `DEV.QUEUE.1`, and mqweb server availability.

**Java consumer 2035:** Check MQ_APP_PASSWORD / `app` permissions, SVRCONN channel CHLAUTH and MQ_USER. `app` must be allowed on queue and queue manager.

**Java consumer build fails:** Check Maven dependencies, internet access to Maven Central, and Java 17. This repository's Java source has not been compiled in the authoring environment.

**Payment stays PENDING:** Check publisher log and JMS log, then inspect MQ queue depth. Do not enable the local worker while diagnosing an MQ-only test.

**Messages repeat:** Some redelivery is expected. Verify a single pair of ledger entries per transfer ID, not that messages never repeat.

**REST TLS error:** A proper CA trust bundle is the correct fix. Disabling verification is acceptable only on this isolated local developer stack.

## Safe failure drill

1. Submit a synthetic payment and capture `transfer_id`.
2. Restart `mq-consumer` around execution: `docker compose --profile ibm restart mq-consumer`.
3. Confirm transfer is `COMPLETED` or `REJECTED` and never debited twice.
4. Submit duplicate `Idempotency-Key`; confirm same transfer ID.
5. Capture sanitized logs and ledger. Never claim crash-in-the-DB-commit-window was exercised unless fault injection actually hit that window.
