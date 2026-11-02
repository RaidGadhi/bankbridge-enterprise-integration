#!/usr/bin/env bash
# IBM MQ Developer mode. Run separately from local mode to ensure MQ is the actual consumer.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f .env ]]; then
  echo 'Run scripts/demo.sh once to create .env, then stop the local worker.' >&2
  exit 1
fi
docker compose --profile local stop local-worker || true
docker compose --profile ibm up -d --build
cat <<'MSG'
IBM MQ Developer environment started (first image download may take time).
Check actual connectivity and transaction processing:
  docker compose --profile ibm logs -f mq mq-dispatcher mq-consumer
  bash scripts/smoke-test.sh
No IBM MQ claims should be made until the above succeeds.
MSG
