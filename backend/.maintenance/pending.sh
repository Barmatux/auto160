#!/usr/bin/env bash
set -euo pipefail

# One-shot: import all diesel Chevrolet Equinox + GMC Terrain from av.by
# (year>=2010, price_usd>=10000, hp<=160). Clears itself from the tree after
# a successful run is expected via deploy-vm.sh removal on the VM.

COMMON=(
  --engine-type diesel
  --creation-date 0
  --year-min 2010
  --price-usd-min 10000
  --max-hp 160
  --max-pages 10
  --per-model-limit 100
  --vin-metadata-limit 0
  --vin-enrich-limit 0
  --trigger manual-diesel-suv
)

echo "==> Import diesel Chevrolet Equinox from av.by"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_avby_listings.py --make Chevrolet --model Equinox "${COMMON[@]}"

echo "==> Import diesel GMC Terrain from av.by"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_avby_listings.py --make GMC --model Terrain "${COMMON[@]}"

echo "==> Diesel Equinox/Terrain import finished"
