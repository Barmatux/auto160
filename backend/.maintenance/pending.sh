#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api python)

echo "==> Refresh BYN prices from av.by API (all existing listings)"
"${COMPOSE[@]}" tools/import_avby_listings.py --refresh-prices-only --max-pages 50 --trigger maintenance

echo "==> Refresh remaining mismatched prices from av.by pages (listing 21763 and similar)"
"${COMPOSE[@]}" tools/refresh_listing_prices_from_avby.py --listing-id 21763
