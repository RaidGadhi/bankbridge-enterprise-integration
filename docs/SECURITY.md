# Security and threat model

**Classification:** learning/demo only; no real user, money, financial institution or regulated payment processing.

### Threat: unauthorized payment creation
Demo uses `X-API-Key` checked server-side with constant-time comparison. **Not sufficient for production.** Real deployment: OAuth 2.0/OIDC with scoped clients, proof-of-possession or mTLS as appropriate; configure IBM API Connect authentication, threat protection and rate limits; authorize ownership of each source account.

### Threat: unauthorized internal processing
The internal endpoint requires `X-Internal-Token`; move it to an internal-only route/service and use mTLS + workload identity in production. Secrets must be managed through Kubernetes Secrets backed by a secret manager, not committed YAML.

### Threat: message interception/tampering
Local MQ/JMS demonstration uses non-TLS development settings and REST verification of self-signed TLS can be disabled; this is **only safe in an isolated developer network**. Real IBM MQ: TLS + verified CA, CHLAUTH + least privilege, and no admin account for message publication.

### Threat: double processing / replay
Request fingerprint and unique key protect API replay. Row locks and terminal DB state protect against JMS redelivery. These controls do **not** defend against malicious clients using fresh keys; authorization and risk controls are missing.

### Threat: data exposure
Only synthetic accounts. Avoid logging full message payloads in production. Current demo logs transfer UUID, status, and event ID. JMS quarantine currently preserves the offending message payload in DEV.QUEUE.2: only use synthetic messages; encrypt and restrict dead-letter access for real systems.

### Threat: denial of service / cost exhaustion
Local API has no rate limiter or WAF. API Connect policies should enforce quotas, payload size constraints, IP controls and authentication. Account creation is intentionally not exposed.

### Threat: unsafe deployment
Use maintained base images, pinned build dependencies, image scanning, SBOM, least-privileged OpenShift service accounts, NetworkPolicies, proper ingress egress allowlists, database TLS, and backups. Demo uses simple `create_all` startup instead of migrations; deploy Alembic schema migrations and tested rollback before any shared environment.

### Explicit non-goals
No PCI-DSS, SAMA, NCA ECC, ISO 27001, HA, DR, zero-trust or production-readiness certification is claimed. This is an architecture exercise, not a financial product.
