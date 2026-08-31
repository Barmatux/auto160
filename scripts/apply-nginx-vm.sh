#!/usr/bin/env bash
# Apply repo nginx config on the VM (canonical https://auto160.by).
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/auto160}"
SRC="$APP_DIR/scripts/nginx-auto160.conf"
AVAILABLE="/etc/nginx/sites-available/auto160"
ENABLED="/etc/nginx/sites-enabled/auto160"

if [[ ! -f "$SRC" ]]; then
  echo "Missing nginx config: $SRC"
  exit 1
fi

run() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    sudo --preserve-env=APP_DIR "$@"
  else
    echo "Need root or passwordless sudo to update nginx."
    echo "Run manually:"
    echo "  sudo APP_DIR='$APP_DIR' bash '$APP_DIR/scripts/apply-nginx-vm.sh'"
    exit 1
  fi
}

echo "==> Install nginx site config from $SRC"
run mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
run cp "$SRC" "$AVAILABLE"
run ln -sfn "$AVAILABLE" "$ENABLED"

# Remove other auto160 site links so server_name blocks do not clash.
shopt -s nullglob
for link in /etc/nginx/sites-enabled/*; do
  name="$(basename "$link")"
  if [[ "$name" == "auto160" ]]; then
    continue
  fi
  if grep -Eq 'auto160\.(by|ru)' "$link" 2>/dev/null; then
    echo "Disabling conflicting site: $link"
    run rm -f "$link"
  fi
done
for conf in /etc/nginx/conf.d/*.conf; do
  if grep -Eq 'auto160\.(by|ru)' "$conf" 2>/dev/null; then
    echo "Disabling conflicting conf.d file: $conf"
    run mv "$conf" "${conf}.bak.$(date +%Y%m%d%H%M%S)"
  fi
done
shopt -u nullglob

# Drop default site if it steals requests.
if [[ -e /etc/nginx/sites-enabled/default ]]; then
  run rm -f /etc/nginx/sites-enabled/default
fi

echo "==> nginx -t"
run nginx -t

echo "==> reload nginx"
run systemctl reload nginx

echo "Nginx config applied (canonical https://auto160.by)."
