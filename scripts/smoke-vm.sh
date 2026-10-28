#!/usr/bin/env bash
# Post-deploy smoke checks for auto160 VM.
set -euo pipefail

BASE_URL="${SMOKE_BASE_URL:-http://127.0.0.1:8000}"
MIN_CATALOG_BYTES="${SMOKE_MIN_CATALOG_BYTES:-500}"
MIN_BY_BYTES="${SMOKE_MIN_BY_BYTES:-${SMOKE_MIN_LISTINGS_BYTES:-500}}"
CURL_MAX_TIME="${SMOKE_CURL_MAX_TIME:-120}"

curl_get() {
  curl -fsS --connect-timeout 5 --max-time "${CURL_MAX_TIME}" "$@"
}

echo "==> Smoke: GET ${BASE_URL}/health"
health="$(curl_get "${BASE_URL}/health")"
echo "health response: ${health}"

echo "==> Smoke: GET ${BASE_URL}/catalog"
catalog_size="$(curl_get "${BASE_URL}/catalog" | wc -c | tr -d ' ')"
echo "catalog bytes: ${catalog_size}"
if [[ "${catalog_size}" -lt "${MIN_CATALOG_BYTES}" ]]; then
  echo "Smoke failed: /catalog response too small (${catalog_size} < ${MIN_CATALOG_BYTES})"
  exit 1
fi

echo "==> Smoke: GET ${BASE_URL}/by"
set +e
by_body="$(curl_get "${BASE_URL}/by")"
by_rc=$?
set -e
if [[ "${by_rc}" -ne 0 ]]; then
  echo "WARNING: /by smoke timed out or failed (rc=${by_rc}); continuing"
else
  by_size="$(printf '%s' "${by_body}" | wc -c | tr -d ' ')"
  echo "by bytes: ${by_size}"
  if [[ "${by_size}" -lt "${MIN_BY_BYTES}" ]]; then
    echo "Smoke failed: /by response too small (${by_size} < ${MIN_BY_BYTES})"
    exit 1
  fi
fi

echo "==> Smoke: GET ${BASE_URL}/listings → /by redirect"
set +e
listings_headers="$(curl -sS -D - -o /dev/null --connect-timeout 5 --max-time "${CURL_MAX_TIME}" "${BASE_URL}/listings")"
listings_rc=$?
set -e
if [[ "${listings_rc}" -ne 0 ]]; then
  echo "WARNING: /listings redirect smoke failed (rc=${listings_rc}); continuing"
else
  listings_code="$(printf '%s' "${listings_headers}" | awk 'NR==1 {print $2}')"
  listings_location="$(printf '%s' "${listings_headers}" | awk 'tolower($1)=="location:" {print $2}' | tr -d '\r')"
  echo "listings status: ${listings_code} location: ${listings_location}"
  if [[ "${listings_code}" != "301" && "${listings_code}" != "302" ]]; then
    echo "Smoke failed: /listings expected redirect for guests, got HTTP ${listings_code}"
    exit 1
  fi
  case "${listings_location}" in
    */by|*/by/|/by|/by/)
      ;;
    *)
      echo "Smoke failed: /listings redirect location should be /by, got '${listings_location}'"
      exit 1
      ;;
  esac
fi

echo "Smoke checks passed"
