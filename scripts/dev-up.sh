#!/usr/bin/env bash
# Bring up the full dev stack and run the integration test suite.
# Usage: ./scripts/dev-up.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Boot the dev stack (api + web + Postgres + Redis + MailHog).
docker compose up -d

echo "Waiting for API to become healthy..."
for i in {1..30}; do
  if curl -sf http://localhost:8000/healthz >/dev/null 2>&1; then
    echo "API is up."
    break
  fi
  sleep 2
done

echo "Waiting for web to become healthy..."
for i in {1..30}; do
  if curl -sf http://localhost:3000/ >/dev/null 2>&1; then
    echo "Web is up."
    break
  fi
  sleep 2
done

echo "Running integration tests..."
RUN_INTEGRATION=1 (cd services/api && ./.venv/bin/python -m pytest tests/integration -q)

echo "Done."
echo "  API:    http://localhost:8000/docs"
echo "  Web:    http://localhost:3000"
echo "  Mail:   http://localhost:8025"
