#!/usr/bin/env bash
# Deploy Auto160 RF reachability test site (nginx on :80).
# Usage on VPS as root: bash deploy-rf-test.sh [PUBLIC_IP]
set -euo pipefail

PUBLIC_IP="${1:-$(curl -4 -fsS --connect-timeout 3 --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')}"
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq nginx curl ca-certificates python3

mkdir -p /var/www/rf-test

cat > /var/www/rf-test/index.html <<HTML
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Auto160 RF access test</title>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 640px; margin: 40px auto; padding: 0 16px; }
    code { background: #f2f2f2; padding: 2px 6px; border-radius: 4px; }
    img { max-width: 100%; height: auto; border: 1px solid #ddd; }
    .ok { color: #0a7a2f; font-weight: 700; font-size: 1.4rem; }
  </style>
</head>
<body>
  <p class="ok">OK</p>
  <h1>Auto160 RF access test</h1>
  <p>Host: <code>${PUBLIC_IP}</code></p>
  <p>If you see this page and the image below from RF, HTTP reachability works.</p>
  <p><img src="/test.png" width="320" height="180" alt="test image" /></p>
  <p>Also check <a href="/ping">/ping</a>.</p>
</body>
</html>
HTML

python3 - <<'PY'
import struct, zlib
w, h = 320, 180
row = b"\x00" + bytes([30, 90, 200]) * w
raw = row * h

def chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

png = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    + chunk(b"IDAT", zlib.compress(raw, 9))
    + chunk(b"IEND", b"")
)
open("/var/www/rf-test/test.png", "wb").write(png)
print("png_bytes", len(png))
PY

rm -f /etc/nginx/sites-enabled/default
cat > /etc/nginx/sites-available/rf-test <<'NGINX'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;
    root /var/www/rf-test;
    index index.html;

    location = /ping {
        default_type text/plain;
        add_header X-Auto160-Test "rf-ok" always;
        return 200 "auto160-rf-test-42\n";
    }

    location / {
        try_files $uri $uri/ =404;
        add_header Cache-Control "no-store";
        add_header X-Auto160-Test "rf-ok" always;
    }
}
NGINX
ln -sfn /etc/nginx/sites-available/rf-test /etc/nginx/sites-enabled/rf-test
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH >/dev/null 2>&1 || true
  ufw allow 80/tcp >/dev/null 2>&1 || true
  ufw allow 443/tcp >/dev/null 2>&1 || true
fi

ss -tlnp | grep -E ':80|:443' || true
curl -fsS -o /dev/null -w "local_index:%{http_code}\n" http://127.0.0.1/
curl -fsS http://127.0.0.1/ping
curl -fsS -o /dev/null -w "local_png:%{http_code} size:%{size_download}\n" http://127.0.0.1/test.png
echo "DONE host=${PUBLIC_IP}"
