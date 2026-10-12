#!/usr/bin/env bash
# Apply repo nginx config on the VM.
# Uses TLS config when Let's Encrypt certs exist; otherwise HTTP bootstrap for IP access.
set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/auto160}"
TLS_SRC="$APP_DIR/scripts/nginx-auto160.conf"
HTTP_SRC="$APP_DIR/scripts/nginx-auto160-http.conf"
AVAILABLE="/etc/nginx/sites-available/auto160"
ENABLED="/etc/nginx/sites-enabled/auto160"
CERT_RU="/etc/letsencrypt/live/auto160.ru/fullchain.pem"

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

if [[ -f "$CERT_RU" && -f "$TLS_SRC" ]]; then
  SRC="$TLS_SRC"
  MODE="tls"
elif [[ -f "$HTTP_SRC" ]]; then
  SRC="$HTTP_SRC"
  MODE="http-bootstrap"
else
  echo "Missing nginx config (need $TLS_SRC or $HTTP_SRC)"
  exit 1
fi

echo "==> Install nginx site config from $SRC ($MODE)"
run mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled
run cp "$SRC" "$AVAILABLE"
run ln -sfn "$AVAILABLE" "$ENABLED"

# Remove other auto160 / rf-test site links so server_name blocks do not clash.
shopt -s nullglob
for link in /etc/nginx/sites-enabled/*; do
  name="$(basename "$link")"
  if [[ "$name" == "auto160" ]]; then
    continue
  fi
  if [[ "$name" == "rf-test" ]] || grep -Eq 'auto160\.(by|ru)|rf-test|/var/www/rf-test' "$link" 2>/dev/null; then
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

if [[ -e /etc/nginx/sites-enabled/default ]]; then
  run rm -f /etc/nginx/sites-enabled/default
fi

echo "==> nginx -t"
run nginx -t

echo "==> reload nginx"
run systemctl reload nginx

if [[ "$MODE" == "tls" ]]; then
  echo "Nginx config applied (canonical https://auto160.ru)."
else
  echo "Nginx HTTP bootstrap applied (no LE certs yet). After DNS → this host, run certbot then re-apply."
fi
