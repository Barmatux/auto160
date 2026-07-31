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
mkdir -p "$APP_DIR/logs"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it once on the VM: cp .env.vm.example .env.vm"
  exit 1
fi

echo "==> Ensure PUBLIC_SITE_URL canonical host"
CANONICAL_SITE_URL="https://auto160.by"
if grep -qE '^[[:space:]]*PUBLIC_SITE_URL=' "$ENV_FILE"; then
  sed -i "s|^[[:space:]]*PUBLIC_SITE_URL=.*|PUBLIC_SITE_URL=${CANONICAL_SITE_URL}|" "$ENV_FILE"
else
  printf '\nPUBLIC_SITE_URL=%s\n' "$CANONICAL_SITE_URL" >> "$ENV_FILE"
fi
grep -E '^PUBLIC_SITE_URL=' "$ENV_FILE"

echo "==> Apply nginx canonical redirects"
if bash "$APP_DIR/scripts/apply-nginx-vm.sh"; then
  echo "Nginx updated"
else
  echo "WARNING: nginx apply failed (sudo/root required). Update manually with scripts/apply-nginx-vm.sh"
fi

echo "==> Remove stale compose containers (name conflicts after partial deploys)"
docker ps -a --format '{{.Names}}' | grep '_auto160-' | xargs -r docker rm -f || true

echo "==> Rebuild and restart containers"
docker compose --env-file .env.vm -f docker-compose.vm.yml up --build -d --remove-orphans

echo "==> Container status"
docker compose --env-file .env.vm -f docker-compose.vm.yml ps

echo "==> Health check"
for attempt in 1 2 3 4 5; do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    echo "API is healthy"
    break
  fi
  echo "Waiting for API... ($attempt/5)"
  sleep 3
  if [[ "$attempt" -eq 5 ]]; then
    echo "Health check failed"
    docker compose --env-file .env.vm -f docker-compose.vm.yml logs --tail=80 api
    exit 1
  fi
done

echo "==> Smoke tests"
bash "$APP_DIR/scripts/smoke-vm.sh"

exit 0
