#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1; then
  echo 'ERROR: Docker with the compose plugin is required; see README.md' >&2
  exit 1
fi
if [[ ! -f .env ]]; then
  python3 - <<'PY'
import secrets
from pathlib import Path
names = ["POSTGRES_PASSWORD", "BANKBRIDGE_API_KEY", "BANKBRIDGE_INTERNAL_TOKEN", "MQ_ADMIN_PASSWORD", "MQ_APP_PASSWORD"]
Path(".env").write_text("\n".join(f"{name}={secrets.token_urlsafe(24)}" for name in names) + "\nMQ_TLS_VERIFY=false\n")
Path(".env").chmod(0o600)
print("Created private randomized .env; keep it off GitHub")
PY
fi
docker compose --profile local up -d --build
printf '\nWaiting for readiness'
for n in $(seq 1 60); do
  if curl --silent --fail http://127.0.0.1:8000/health/ready >/dev/null; then
    printf '\nBankBridge ready at http://127.0.0.1:8000/docs\n'
    exec bash scripts/smoke-test.sh
  fi
  printf '.'
  sleep 2
done
printf '\nAPI did not become ready. Inspect: docker compose logs api db local-worker\n' >&2
exit 1
