#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-${PROD_APP_DIR:-$HOME/ClinicalProfileAgent}}"
BRANCH="${2:-main}"

cd "$APP_DIR"

echo "[deploy] Syncing repository on branch $BRANCH"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

echo "[deploy] Rebuilding and restarting production services"
docker compose -f docker-compose.prod.yml up -d --build

echo "[deploy] Waiting for API health"
for attempt in $(seq 1 20); do
  if curl --fail --silent http://127.0.0.1:8000/health > /dev/null; then
    echo "[deploy] API healthy"
    exit 0
  fi
  sleep 3
done

echo "[deploy] API health check failed"
docker compose -f docker-compose.prod.yml logs api --tail=200
exit 1
