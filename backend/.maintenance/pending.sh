#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api python)

echo "==> Fix listing prices stored as RUB instead of BYN"
"${COMPOSE[@]}" tools/backfill_listing_prices_byn.py
