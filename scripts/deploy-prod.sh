#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${1:-$HOME/LawAskLLM}"
BRANCH="${2:-main}"

cd "$ROOT_DIR"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "==> Deploy branch: ${BRANCH}"
git fetch --all --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

echo "==> Rebuild and restart services"
"${DC[@]}" up -d --build --remove-orphans

echo "==> Backend health check"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:18081/health" >/dev/null; then
    echo "==> Health check passed"
    exit 0
  fi
  sleep 2
done

echo "==> Health check failed, recent backend logs:"
"${DC[@]}" logs --tail=200 backend || true
exit 1
