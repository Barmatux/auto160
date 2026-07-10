#!/usr/bin/env bash
# View auto160 logs on VM without entering a container.
#
# Usage:
#   bash scripts/logs-vm.sh              # tail api.log (last 200 lines, follow)
#   bash scripts/logs-vm.sh avby-sync 500
#   bash scripts/logs-vm.sh docker api 100   # docker compose logs -f
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/auto160}"
BACKEND_DIR="$APP_DIR/backend"
LOG_DIR="$APP_DIR/logs"
MODE="${1:-file}"
SERVICE="${2:-api}"
LINES="${3:-200}"

usage() {
  echo "Usage:"
  echo "  $0 [file] [SERVICE] [LINES]     tail ~/auto160/logs/SERVICE.log"
  echo "  $0 docker [SERVICE] [LINES]     docker compose logs -f"
  echo "Services: api, avby-sync, avby-vin-session"
}

if [[ "$MODE" == "-h" || "$MODE" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$MODE" == "docker" ]]; then
  cd "$BACKEND_DIR"
  docker compose --env-file .env.vm -f docker-compose.vm.yml logs -f --tail="$LINES" "$SERVICE"
  exit 0
fi

# file mode: first arg may be service name
if [[ "$MODE" == "api" || "$MODE" == "avby-sync" || "$MODE" == "avby-vin-session" ]]; then
  SERVICE="$MODE"
  LINES="${2:-200}"
fi

LOG_FILE="$LOG_DIR/$SERVICE.log"
if [[ ! -f "$LOG_FILE" ]]; then
  echo "Log file not found: $LOG_FILE"
  echo "Try: $0 docker $SERVICE"
  ls -la "$LOG_DIR" 2>/dev/null || echo "Directory $LOG_DIR does not exist yet"
  exit 1
fi

echo "==> tail -n $LINES -f $LOG_FILE"
tail -n "$LINES" -f "$LOG_FILE"
