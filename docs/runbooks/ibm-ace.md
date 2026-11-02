# IBM App Connect Enterprise (ACE) — integration extension

**Important:** `deploy/ace/BankBridge_ValidateAndMap.esql` is a **starter source file**, not a verified `.msgflow` or `.bar`. The core MQ-to-API path works without ACE; this optional extension is how to place a genuine ACE broker into the flow after obtaining IBM ACE Toolkit/Developer edition.

## Planned deployment topology

Without ACE: Outbox publisher -> `DEV.QUEUE.1` -> Java JMS consumer -> transaction API.

With ACE: Outbox publisher -> **ACE MQInput on `DEV.QUEUE.1`** -> Compute validation/mapping -> **ACE MQOutput on `DEV.QUEUE.3`** -> Java JMS consumer -> transaction API.

## Toolkit construction procedure

1. Install permitted IBM App Connect Enterprise Toolkit / Developer edition, along with IBM MQ connectivity configuration. Understand developer edition evaluation limits and license conditions.
2. Create an ACE **Application** named `BankBridgeIntegration` and a **Message Flow** named `RoutePaymentRequested`.
3. Add `MQInput`, `Compute`, and `MQOutput` nodes in that order. Assign queue manager `QM1` and input queue `DEV.QUEUE.1`; the output queue should be `DEV.QUEUE.3`. Configure parse domain `JSON` where required.
4. Create Compute node named `ValidateAndMap`; paste `BankBridge_ValidateAndMap.esql` and associate its `ValidateAndMap_Compute` module. Check ESQL syntax and exception handling in the Toolkit. Add error terminals, logging and appropriate message transactions based on your ACE version.
5. Build a BAR with the Toolkit or the supported build tool; resolve errors before committing integration artifacts (never commit proprietary IBM binaries or credentials).
6. **Before** running ACE, configure the Java JMS consumer to receive on the new output queue by setting `MQ_CONSUME_QUEUE=DEV.QUEUE.3` in `.env`. Restart MQ consumer: `docker compose --profile ibm up -d --force-recreate mq-consumer`.
7. Start ACE integration server with the built BAR using a properly licensed runtime. Run smoke tests and verify queues, transformations and error terminal behavior.
8. Capture broker traces/sanitized screenshots, and only then update the README Verification section to 'tested'.

## Architectural considerations

For real integration, add schema validation, error capture and DLQ routing, MQ transaction support, ACE trace/correlation IDs, API Connect policies, and observability. Do not run an ACE MQInput and the direct JMS worker against the **same queue**: they will compete for messages and the ACE mapping is bypassed on some requests. The separate destination queue fixes that.

[IBM App Connect Enterprise ESQL overview](https://www.ibm.com/docs/en/app-connect/13.0.x?topic=files-creating-esql-node)
