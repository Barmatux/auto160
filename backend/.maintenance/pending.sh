#!/usr/bin/env bash
set -euo pipefail

echo "==> Remove Fiat Tipo generation I from catalog and listings"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/remove_catalog_generation.py \
  --make Fiat \
  --model Tipo \
  --generation I
