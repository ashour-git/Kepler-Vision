#!/usr/bin/env bash
# Local CI runner. Runs the same gates as GitHub Actions.
# Usage: ./scripts/ci.sh [api|web|ml|all]
#
# Requires: pnpm, python 3.12+, docker (for integration tests)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${1:-all}"

run_api() {
  echo "==> API: unit tests"
  (cd services/api && ./.venv/bin/python -m pytest tests/unit tests/smoke -q)
}

run_web() {
  echo "==> WEB: typecheck + unit tests"
  (cd apps/web && pnpm typecheck)
  (cd apps/web && pnpm test)
}

run_ml() {
  echo "==> ML: unit tests"
  (cd services/ml && ./.venv/bin/python -m pytest tests/unit -q)
}

run_integration() {
  echo "==> API: integration tests (require Postgres + Redis)"
  RUN_INTEGRATION=1 (cd services/api && ./.venv/bin/python -m pytest tests/integration -q)
}

run_lint() {
  echo "==> Lint: ruff (api + ml)"
  (cd services/api && ruff check src tests || true)
  (cd services/ml && ruff check src tests || true)
}

case "$TARGET" in
  api)
    run_api
    ;;
  web)
    run_web
    ;;
  ml)
    run_ml
    ;;
  integration)
    run_integration
    ;;
  lint)
    run_lint
    ;;
  all)
    run_lint
    run_api
    run_web
    run_ml
    ;;
  *)
    echo "Usage: $0 [api|web|ml|integration|lint|all]" >&2
    exit 1
    ;;
esac
