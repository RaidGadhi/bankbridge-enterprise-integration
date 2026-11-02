# OpenShift demo deployment

`deploy/openshift/bankbridge.yaml` contains API resources but does **not** create a database, build a container image, provision a Kafka topic, establish HA or install IBM CP4I operators.

### Preconditions

* Have a genuine OpenShift cluster (`oc` logged in), registry credentials and an externally reachable PostgreSQL instance with TLS.
* Build image using `docker build -t <registry>/bankbridge/api:1.0.0 .` and push it.
* Update the placeholder image in `bankbridge.yaml`. Do not blindly apply example secrets with `REPLACE_ME` values.
* Initialize schema/migrations as documented for your target DB; this demo runs `Base.metadata.create_all` on startup only and is **not** a schema-migration framework.

### Steps

```bash
oc new-project bankbridge-demo
oc create secret generic bankbridge-secrets \
  --from-literal=DATABASE_URL='postgresql+psycopg://USER:PASSWORD@POSTGRES_HOST:5432/bankbridge' \
  --from-literal=BANKBRIDGE_API_KEY='REPLACE_WITH_RANDOM_SECRET' \
  --from-literal=BANKBRIDGE_INTERNAL_TOKEN='REPLACE_WITH_RANDOM_SECRET'
oc apply -f deploy/openshift/bankbridge.yaml
oc rollout status deployment/bankbridge-api
oc get pods,svc,route
```

This documentation intentionally uses visible placeholders rather than live credentials. For actual deployments, use secret-manager integration instead of literal values on command lines (shell history exposes secrets).

### Caveats

* Routes must reach the pods under your cluster's ingress-network policy; adjust `NetworkPolicy` to your real OpenShift ingress namespace, not an arbitrary wide-allow policy.
* The container uses a fixed unprivileged UID; your cluster's SCC/UID range may require an image-specific permissions adjustment.
* `replicas: 2` protects only stateless API pods. Without resilient PostgreSQL, MQ/Kafka, ingress and network dependencies, **this is not high availability**.
* The `/internal/process/` endpoint is on the same service as public routes and only guarded by a demo token. Restrict to internal ingress/mTLS in any serious deployment.
* Deploy MQ/Kafka publishers and consumers separately and wire the corresponding secrets/roles after testing.
