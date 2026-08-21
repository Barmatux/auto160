#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api python)

echo "==> Refresh BYN price for listing 21763 from av.by page"
"${COMPOSE[@]}" tools/refresh_listing_prices_from_avby.py --listing-id 21763 --delay 0

echo "==> Refresh BYN prices for Peugeot 308 listings via av.by API"
"${COMPOSE[@]}" tools/import_avby_listings.py --refresh-prices-only --make Peugeot --model 308 --max-pages 20 --trigger maintenance
