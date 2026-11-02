# Portfolio positioning — truthful, specific, valuable

## GitHub summary
BankBridge is a synthetic enterprise banking integration prototype exploring API-led and event-driven architectures: durable outbox, request and processing idempotency, IBM MQ transactional messaging adapters, Kafka event publication, and OpenShift deployment patterns.

## CV entry (safe now)
**BankBridge — Enterprise Integration Architecture (Independent Project)**
- Developed a reproducible synthetic payment integration API with PostgreSQL-compatible transactional ledger logic, durable outbox, immutable idempotency keys and failure-safe retry behavior.
- Implemented an IBM MQ REST publisher and Java JMS transactional consumer adapter, with deployment profiles and automated tests for the Python core.
- Authored architectural decision records, a security threat model, OpenAPI contract, IBM ACE ESQL example and OpenShift manifests to document enterprise integration patterns.

## Expand ONLY after runtime validation
- Validated end-to-end IBM MQ persistent messaging with transactional JMS consumption and duplicate-delivery recovery.
- Deployed Kafka terminal-event publication to IBM Event Streams and demonstrated downstream processing.
- Imported payment APIs into IBM API Connect and deployed an ACE flow and OpenShift services.

## Interview walkthrough (6 minutes)
1. Why this architecture: bank-facing APIs must accept retries and withstand crashes.
2. Payment POST and idempotency proof.
3. PostgreSQL terminal-state logic, row locks and double-entry balances.
4. Outbox publication and redelivery failure matrix.
5. Explain why MQ REST PUT + transacted JMS receive was chosen.
6. State exact runtime validation done, including what is still missing.

## Avoid these phrases
* "Implemented full production IBM Cloud Pak for Integration" — untrue.
* "Achieved exactly-once message delivery" — untrue; only ledger *effects* are idempotent.
* "Delivered PCI/SAMA-compliant banking platform" — untrue.
* "Deployed on OpenShift" — until deployment is actually tested.
