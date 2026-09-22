#!/usr/bin/env bash
set -euo pipefail

echo "==> Remove Mercedes-Benz 1.6 diesel 160 hp (2016+) from catalog/listings"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/remove_mercedes_16_diesel_160.py
