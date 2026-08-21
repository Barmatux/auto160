#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Import catalog generations (Peugeot 2008 II, 308 III, BMW F30, Hyundai Venue)"
python tools/import_avby.py --urls-file data/catalog_generations_batch_20260821.txt

echo "==> Apply ratings for imported generations"
python tools/import_catalog_ratings.py data/catalog_generations_ratings_20260821.json

echo "==> Restore archived listings now matching catalog scope"
python tools/restore_archived_catalog_scope_listings.py --relink
