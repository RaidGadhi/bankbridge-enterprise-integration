# Event Streams / Kafka publisher

A terminal transfer outcome is saved in the database outbox when the ledger transaction commits. The optional `bankbridge.events` worker finds unpublished `payment.completed` / `payment.rejected` rows, sends them to Kafka with `acks=all`, then marks the rows published in the database. The event key is `transfer_id`.

1. Provision a Kafka/IBM Event Streams cluster and create `bankbridge.payments.v1` topic.
2. Create a service credential with write permission and TLS access.
3. Put `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_USERNAME`, `KAFKA_PASSWORD`, protocol/mechanism and topic into an ignored local `.env` or a proper secret store.
4. Start `docker compose --profile events up -d --build` (also starts required API/DB). Use `--profile local` too if testing without MQ: `docker compose --profile local --profile events up -d --build`.
5. Post a synthetic transfer and verify it completes; inspect `docker compose --profile events logs -f event-publisher` and a Kafka topic consumer.

### Delivery guarantees

If Kafka acknowledges but the SQL outbox update fails, the event will publish again after restart. Downstream services must deduplicate by `(event_type, transfer_id)` before applying side effects. Kafka acks do not make database and broker transactions atomic. This is not end-to-end exactly-once delivery.

### Profile use

Do not use `--profile ibm` and `--profile local` simultaneously if you want to prove the event came through MQ. `events` is independent and can run alongside either one.
