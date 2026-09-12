# External Market Prices API (avg BYN by brand/model/year)

Public base: `https://auto160.ru/api/v1/market`

Auth: header `X-Api-Key: <MARKET_PRICES_API_KEY>`.

## auto160 setup

1. In `backend/.env.vm` set:
   - `MARKET_PRICES_API_KEY=<long random>`
   - optional `MARKET_PRICES_ALLOWED_IPS=1.2.3.4,10.0.0.0/8` (empty = any IP with valid key)
2. Ensure listing averages are recomputed (`tools/recompute_listing_avg_prices.py` / post av.by sync).
3. Restart API.

Unlike `/api/v1/internal/`, this path is **public** (nginx `location /`). Protect with the API key (and optional IP allowlist).

## Endpoints

### `GET /avg-prices`

List averages with optional filters.

| Query | Notes |
|-------|--------|
| `brand` | Case-insensitive |
| `model` | Normalized (`3 series` → `3 серия`) |
| `year` | Exact year |
| `window_days` | `30`, `60`, or `90`; omit for all |
| `min_samples` | Default `11` (rows with fewer samples omitted) |
| `limit` / `offset` | Pagination (`limit` max 500) |

Example:

```bash
curl -sS -H "X-Api-Key: $MARKET_PRICES_API_KEY" \
  "https://auto160.ru/api/v1/market/avg-prices?brand=BMW&model=X1&window_days=90&limit=50"
```

### `GET /avg-prices/lookup`

One brand/model/year (required). Returns matching windows (or one if `window_days` set).

```bash
curl -sS -H "X-Api-Key: $MARKET_PRICES_API_KEY" \
  "https://auto160.ru/api/v1/market/avg-prices/lookup?brand=BMW&model=X1&year=2015&window_days=90"
```

## Response shape

```json
{
  "total": 1,
  "limit": 100,
  "offset": 0,
  "items": [
    {
      "brand": "BMW",
      "model": "X1",
      "year": 2015,
      "window_days": 90,
      "avg_price_byn": "18500.00",
      "min_price_byn": "12000.00",
      "max_price_byn": "24000.00",
      "sample_count": 14,
      "sample_count_raw": 16,
      "outliers_removed": 2,
      "currency": "BYN",
      "window_start": "2026-06-01T00:00:00",
      "window_end": "2026-09-01T00:00:00",
      "computed_at": "2026-09-01T12:00:00"
    }
  ]
}
```

Prices are BYN market averages from active av.by-synced listings (IQR outlier trim). Empty `items` means no row met `min_samples` for that key/window.
