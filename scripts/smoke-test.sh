#!/usr/bin/env bash
# One end-to-end synthetic transfer against the running local Docker demo.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a
source .env
set +a
export BANKBRIDGE_API_KEY
python3 - <<'PY'
import json, os, time, uuid
from urllib.request import Request, urlopen
api = "http://127.0.0.1:8000"
key = os.environ["BANKBRIDGE_API_KEY"]
headers = {"Content-Type":"application/json", "X-API-Key":key}
def req(method, route, body=None, extra=None):
    data = json.dumps(body).encode() if body is not None else None
    r = Request(api+route, data=data, headers={**headers, **(extra or {})}, method=method)
    with urlopen(r, timeout=10) as resp: return json.loads(resp.read())
a_before = req("GET", "/v1/accounts/DEMO-100")
b_before = req("GET", "/v1/accounts/DEMO-200")
amount = "12.34"
payload = {"from_account":"DEMO-100", "to_account":"DEMO-200", "amount":amount, "currency":"SAR"}
idem = "smoke-"+str(uuid.uuid4())
r = req("POST", "/v1/transfers", payload, {"Idempotency-Key":idem})
print("Submitted transfer:", r["transfer_id"])
for _ in range(30):
    r = req("GET", "/v1/transfers/"+r["transfer_id"])
    if r["status"] != "PENDING": break
    time.sleep(1)
assert r["status"] == "COMPLETED", "Not completed: " + str(r)
replay = req("POST", "/v1/transfers", payload, {"Idempotency-Key":idem})
assert replay["transfer_id"] == r["transfer_id"]
from decimal import Decimal
assert Decimal(req("GET", "/v1/accounts/DEMO-100")["balance"]) == Decimal(a_before["balance"])-Decimal(amount)
assert Decimal(req("GET", "/v1/accounts/DEMO-200")["balance"]) == Decimal(b_before["balance"])+Decimal(amount)
print("SUCCESS: single debit + credit, replay uses same transfer, status=COMPLETED")
print("API docs:", api+"/docs")
PY
