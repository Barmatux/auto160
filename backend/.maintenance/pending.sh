#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE=(docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api python)

echo "==> Import catalog generations (Peugeot 2008 II, 308 III, BMW F30, Hyundai Venue)"
"${COMPOSE[@]}" tools/import_avby.py --urls-file data/catalog_generations_batch_20260821.txt

echo "==> Apply ratings for imported generations"
"${COMPOSE[@]}" tools/import_catalog_ratings.py data/catalog_generations_ratings_20260821.json

echo "==> Restore archived listings now matching catalog scope"
"${COMPOSE[@]}" tools/restore_archived_catalog_scope_listings.py --relink
