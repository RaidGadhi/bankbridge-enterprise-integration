# IBM API Connect import procedure

**Scope:** The checked-in `deploy/apiconnect/bankbridge-openapi.yaml` is an OpenAPI 3 contract, not a deployed IBM API Connect Product, catalog or gateway policy. It describes the simulated payment API, `Idempotency-Key`, response codes and developer API-key security.

1. Start and verify local demo: `bash scripts/demo.sh`.
2. Get access to an IBM API Connect environment and ensure the gateway can reach the API's service endpoint over TLS. A SaaS API Connect gateway **cannot** call your computer's `127.0.0.1` address.
3. Import `deploy/apiconnect/bankbridge-openapi.yaml` into the API Manager.
4. Configure the `DataPower API Gateway` assembly's target service URL, API key/OAuth policies, TLS validation, access control, payload limits, and quotas.
5. Map gateway authentication/credentials to the backend's `X-API-Key` **securely**, or replace backend key auth with a trusted mTLS/identity mechanism.
6. Publish a test Product/Catalog and validate `202`, `401`, `409`, and `422` using the gateway URL.
7. Record and sanitize tests. Update CV only after executing the import and gateway policies.

The spec's `servers` placeholder `bankbridge.example.invalid` must be replaced by a real test endpoint. API Connect-specific exported Product metadata is deliberately not fabricated.
