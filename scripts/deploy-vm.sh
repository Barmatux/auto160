#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/auto160}"
BACKEND_DIR="$APP_DIR/backend"
COMPOSE_FILE="$BACKEND_DIR/docker-compose.vm.yml"
ENV_FILE="$BACKEND_DIR/.env.vm"
LOCK_FILE="${DEPLOY_LOCK_FILE:-/tmp/auto160-deploy.lock}"

# Serialize CI + manual deploys so concurrent compose down/up cannot race.
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  echo "==> Another deploy holds $LOCK_FILE; waiting up to 20 minutes"
  if ! flock -w 1200 9; then
    echo "ERROR: timed out waiting for deploy lock $LOCK_FILE"
    exit 1
  fi
fi
echo "==> Acquired deploy lock $LOCK_FILE"

if [[ "${SKIP_GIT_PULL:-}" != "1" && ! -d "$APP_DIR/.git" ]]; then
  echo "Git repository not found at $APP_DIR"
  exit 1
fi

cd "$APP_DIR"
if [[ "${SKIP_GIT_PULL:-}" == "1" ]]; then
  echo "==> Skip git pull (code synced by CI)"
else
  echo "==> Pull latest code"
  if ! GIT_TERMINAL_PROMPT=0 git fetch origin master; then
    echo "==> git fetch as $(id -un) failed; retry via sudo"
    sudo -n git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true
    sudo -n GIT_TERMINAL_PROMPT=0 git -C "$APP_DIR" fetch origin master
    sudo -n git -C "$APP_DIR" reset --hard origin/master
  else
    git reset --hard origin/master
  fi
fi

cd "$BACKEND_DIR"
mkdir -p "$APP_DIR/logs"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it once on the VM: cp .env.vm.example .env.vm"
  exit 1
fi

echo "==> Ensure PUBLIC_SITE_URL canonical host"
CANONICAL_SITE_URL="https://auto160.ru"
if grep -qE '^[[:space:]]*PUBLIC_SITE_URL=' "$ENV_FILE"; then
  sed -i "s|^[[:space:]]*PUBLIC_SITE_URL=.*|PUBLIC_SITE_URL=${CANONICAL_SITE_URL}|" "$ENV_FILE"
else
  printf '\nPUBLIC_SITE_URL=%s\n' "$CANONICAL_SITE_URL" >> "$ENV_FILE"
fi
grep -E '^PUBLIC_SITE_URL=' "$ENV_FILE"

echo "==> Apply nginx canonical redirects"
if APP_DIR="$APP_DIR" bash "$APP_DIR/scripts/apply-nginx-vm.sh"; then
  echo "Nginx updated"
else
  echo "WARNING: nginx apply failed (sudo/root required). Update manually:"
  echo "  sudo APP_DIR=$APP_DIR bash $APP_DIR/scripts/apply-nginx-vm.sh"
fi

echo "==> Remove stale compose containers (name conflicts after partial deploys)"
# Compose sometimes leaves hash-prefixed leftovers (e.g. e7d9fec72ba3_auto160-api)
# after interrupted recreates; concurrent manual+CI deploys make this worse.
docker compose --env-file .env.vm -f docker-compose.vm.yml down --remove-orphans || true
docker ps -a --format '{{.Names}}' | grep -E '(^|_)auto160-' | xargs -r docker rm -f || true

echo "==> Rebuild and restart containers"
docker compose --env-file .env.vm -f docker-compose.vm.yml up --build -d --remove-orphans

echo "==> Container status"
docker compose --env-file .env.vm -f docker-compose.vm.yml ps

echo "==> Health check"
# Alembic + multi-worker uvicorn often needs >60s before /health accepts.
HEALTH_ATTEMPTS="${HEALTH_ATTEMPTS:-36}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-5}"
for attempt in $(seq 1 "$HEALTH_ATTEMPTS"); do
  if curl -fsS --connect-timeout 3 --max-time 10 http://127.0.0.1:8000/health >/dev/null; then
    echo "API is healthy"
    break
  fi
  echo "Waiting for API... ($attempt/$HEALTH_ATTEMPTS)"
  sleep "$HEALTH_SLEEP_SECONDS"
  if [[ "$attempt" -eq "$HEALTH_ATTEMPTS" ]]; then
    echo "Health check failed"
    docker compose --env-file .env.vm -f docker-compose.vm.yml ps
    docker compose --env-file .env.vm -f docker-compose.vm.yml logs --tail=120 api
    exit 1
  fi
done

echo "==> Smoke tests"
bash "$APP_DIR/scripts/smoke-vm.sh"

echo "==> Util-sbor exclusions cleanup (Chevrolet Malibu 1.5/160)"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/remove_chevrolet_malibu_15_160.py || echo "WARNING: Malibu util-sbor cleanup failed"

MAINTENANCE_SCRIPT="$BACKEND_DIR/.maintenance/pending.sh"
if [[ -f "$MAINTENANCE_SCRIPT" ]]; then
  echo "==> Run pending maintenance"
  if (
    cd "$BACKEND_DIR"
    bash "$MAINTENANCE_SCRIPT"
  ); then
    rm -f "$MAINTENANCE_SCRIPT"
    echo "Maintenance script completed and removed"
  else
    echo "WARNING: maintenance script failed; leaving $MAINTENANCE_SCRIPT for retry"
  fi
fi

exit 0
