#!/usr/bin/env bash
# Post-deploy smoke checks for auto160 VM.
set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-http://127.0.0.1:8000}"
MIN_CATALOG_BYTES="${SMOKE_MIN_CATALOG_BYTES:-500}"
MIN_LISTINGS_BYTES="${SMOKE_MIN_LISTINGS_BYTES:-500}"

echo "==> Smoke: GET ${BASE_URL}/health"
health="$(curl -fsS "${BASE_URL}/health")"
echo "health response: ${health}"

echo "==> Smoke: GET ${BASE_URL}/catalog"
catalog_size="$(curl -fsS "${BASE_URL}/catalog" | wc -c | tr -d ' ')"
echo "catalog bytes: ${catalog_size}"
if [[ "${catalog_size}" -lt "${MIN_CATALOG_BYTES}" ]]; then
  echo "Smoke failed: /catalog response too small (${catalog_size} < ${MIN_CATALOG_BYTES})"
  exit 1
fi

echo "==> Smoke: GET ${BASE_URL}/listings"
listings_size="$(curl -fsS "${BASE_URL}/listings" | wc -c | tr -d ' ')"
echo "listings bytes: ${listings_size}"
if [[ "${listings_size}" -lt "${MIN_LISTINGS_BYTES}" ]]; then
  echo "Smoke failed: /listings response too small (${listings_size} < ${MIN_LISTINGS_BYTES})"
  exit 1
fi

echo "Smoke checks passed"
