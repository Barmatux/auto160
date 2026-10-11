#!/usr/bin/env bash
# Prepare CloudVPS host for Auto160 (Docker, swap, dirs). Does NOT deploy the app.
# Usage (on the VPS as root):
#   curl -fsSL … | bash   # or copy this script and:
#   bash scripts/bootstrap-cloudvps.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/root/auto160}"
SWAP_MB="${SWAP_MB:-2048}"
MIN_SWAP_MB=1024

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root on the CloudVPS host."
  exit 1
fi

echo "==> Host: $(hostname) $(uname -r)"
echo "==> Memory:"
free -h

echo "==> Ensure swap (>= ${MIN_SWAP_MB}Mi)"
swap_total_mb="$(awk '/SwapTotal:/ {print int($2/1024)}' /proc/meminfo)"
if [[ "$swap_total_mb" -lt "$MIN_SWAP_MB" ]]; then
  SWAPFILE=/swapfile-auto160
  if [[ ! -f "$SWAPFILE" ]]; then
    fallocate -l "${SWAP_MB}M" "$SWAPFILE" || dd if=/dev/zero of="$SWAPFILE" bs=1M count="$SWAP_MB"
    chmod 600 "$SWAPFILE"
    mkswap "$SWAPFILE"
  fi
  if ! swapon --show | grep -q "$SWAPFILE"; then
    swapon "$SWAPFILE"
  fi
  if ! grep -q "$SWAPFILE" /etc/fstab; then
    echo "$SWAPFILE none swap sw 0 0" >> /etc/fstab
  fi
  echo "Swap ready:"
  swapon --show
else
  echo "Swap already ${swap_total_mb}Mi — ok"
fi

echo "==> Packages: curl ca-certificates git"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl ca-certificates git gnupg lsb-release

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Install Docker Engine + Compose plugin"
  install -m 0755 -d /etc/apt/keyrings
  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
  fi
  arch="$(dpkg --print-architecture)"
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  echo "Docker already installed: $(docker --version)"
fi

echo "==> App directory ${APP_DIR}"
mkdir -p "$APP_DIR" "${APP_DIR}/logs" "${APP_DIR}/backend"
# Placeholder so cutover knows where secrets go; never commit real .env.vm
if [[ ! -f "${APP_DIR}/backend/.env.vm" ]]; then
  cat > "${APP_DIR}/backend/.env.vm.PLACEHOLDER" <<'EOF'
# Copy production secrets here as backend/.env.vm before first deploy.
# Source: old VM ~/auto160/backend/.env.vm (scp over SSH) or rebuild from .env.vm.example.
# Critical for CloudVPS:
#   PUBLIC_SITE_URL=https://auto160.ru
#   AUTOPLIUS_SCRAPE_DSN — old 10.129.x private IP will NOT work from this host
#   SMTP_* / S3_* / SECRET_KEY / POSTGRES_PASSWORD — copy from old production
EOF
  echo "Wrote ${APP_DIR}/backend/.env.vm.PLACEHOLDER"
fi

echo "==> UFW (allow SSH + HTTP/HTTPS; leave inactive if already managed)"
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH >/dev/null 2>&1 || true
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
  echo "UFW rules ensured for 22/80/443 (status unchanged):"
  ufw status || true
fi

echo "==> Bootstrap done (app NOT deployed)."
echo "Next: see docs/cloudvps-cutover.md"
docker --version
docker compose version
free -h
