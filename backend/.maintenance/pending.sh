#!/usr/bin/env bash
set -uo pipefail

# One-shot: import diesel Chevrolet Equinox + GMC Terrain from av.by.
# Non-fatal for deploy: log failures but do not abort the whole deploy pipeline.

log() { echo "==> $*"; }

run_one() {
  local make="$1"
  local model="$2"
  log "Import diesel ${make} ${model} from av.by"
  if docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
    python tools/import_avby_listings.py \
      --make "$make" \
      --model "$model" \
      --engine-type diesel \
      --creation-date 0 \
      --year-min 2010 \
      --price-usd-min 10000 \
      --max-hp 160 \
      --max-pages 10 \
      --per-model-limit 100 \
      --vin-metadata-limit 0 \
      --vin-enrich-limit 0 \
      --trigger manual-diesel-suv
  then
    log "OK: ${make} ${model}"
    return 0
  fi
  local code=$?
  log "FAILED: ${make} ${model} (exit ${code})"
  return "$code"
}

status=0
run_one Chevrolet Equinox || status=$?
run_one GMC Terrain || status=$?

if [[ "$status" -ne 0 ]]; then
  log "Diesel Equinox/Terrain import finished with errors (exit ${status})"
  # Keep deploy green so the site stays up; inspect container logs if counts are low.
  exit 0
fi

log "Diesel Equinox/Terrain import finished OK"
exit 0
