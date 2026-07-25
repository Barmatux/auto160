#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-$HOME/auto160/backend/.env.vm}"
COMPOSE_FILE="${2:-$HOME/auto160/backend/docker-compose.vm.yml}"

NEW_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"

if grep -q '^BOOTSTRAP_ADMIN_PASSWORD=' "$ENV_FILE"; then
  sed -i "s|^BOOTSTRAP_ADMIN_PASSWORD=.*|BOOTSTRAP_ADMIN_PASSWORD=$NEW_PASS|" "$ENV_FILE"
else
  echo "BOOTSTRAP_ADMIN_PASSWORD=$NEW_PASS" >> "$ENV_FILE"
fi

cd "$(dirname "$COMPOSE_FILE")"

docker compose -f "$(basename "$COMPOSE_FILE")" exec -T api python <<PY
from app.security import hash_password
from app.db import SessionLocal
from app.models import User

pwd = "$NEW_PASS"
db = SessionLocal()
try:
    user = db.query(User).filter(User.email == "admin@auto160.com").first()
    if not user:
        raise SystemExit("admin user not found")
    user.password_hash = hash_password(pwd)
    db.commit()
    print("DB_UPDATED")
finally:
    db.close()
PY

docker compose -f "$(basename "$COMPOSE_FILE")" up -d api --force-recreate >/dev/null

printf '%s\n' "$NEW_PASS" > "$HOME/.admin_password_new"
chmod 600 "$HOME/.admin_password_new"

echo "LOGIN=admin"
echo "PASSWORD_FILE=$HOME/.admin_password_new"
echo "DONE"
