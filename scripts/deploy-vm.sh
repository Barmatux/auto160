#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/auto160}"
BACKEND_DIR="$APP_DIR/backend"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.vm.yml"
ENV_FILE="$BACKEND_DIR/.env.vm"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Git repository not found at $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
echo "==> Pull latest code"
git fetch origin master
git reset --hard origin/master

cd "$BACKEND_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it once on the VM: cp .env.vm.example .env.vm"
  exit 1
fi

echo "==> Rebuild and restart containers"
docker compose --env-file .env.vm -f docker-compose.vm.yml up --build -d --remove-orphans

echo "==> Container status"
docker compose --env-file .env.vm -f docker-compose.vm.yml ps

echo "==> Health check"
for attempt in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "API is healthy"
    exit 0
  fi
  echo "Waiting for API... ($attempt/5)"
  sleep 3
done

echo "Health check failed"
docker compose --env-file .env.vm -f docker-compose.vm.yml logs --tail=80 api
exit 1
