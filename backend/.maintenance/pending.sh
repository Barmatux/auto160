#!/usr/bin/env bash
set -euxo pipefail

cd "$(dirname "$0")/.."

ARGS=(--make Fiat --model Tipo --generation I)

echo "==> Dry run"
dry_output="$(docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/remove_catalog_generation.py "${ARGS[@]}" --dry-run)"
echo "$dry_output"

if ! echo "$dry_output" | grep -Eq 'catalog_items=[1-9][0-9]*'; then
  echo "ERROR: no catalog items matched for Fiat Tipo I"
  exit 1
fi

echo "==> Apply removal"
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/remove_catalog_generation.py "${ARGS[@]}"
