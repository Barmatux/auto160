# av.by listings → Auto160

## What it does

- **Scrape** runs on scrape-platform (`93.125.82.254`, `/opt/scrape-platform`): adapter `avby` writes to Postgres `listings` with `source=avby`, photos under `avby/{id}/…` in `auto160-media` (`/media/object?key=…`).
- **Auto160** imports via `AUTOPLIUS_SCRAPE_DSN` (`tools/import_avby_scrape_listings.py`): upserts into `car_listings` with `source="av.by"` and `avby_id`, then applies catalog / generation / util-sbor filters locally.
- VIN session (`avby-vin-session`) and nightly archive check (`avby-archive`) stay on Auto160.

## Env (VM `.env.vm`)

```bash
AUTOPLIUS_SCRAPE_DSN=postgresql://scrape:scrape@93.125.82.254:5433/scrape
# same S3 keys as auto24/autoplius (auto160-media)
```

## Scrape-platform

```bash
# on 93.125.82.254
cd /opt/scrape-platform
# Start run via UI or:
curl -X POST http://127.0.0.1:8000/api/v1/runs -H 'Content-Type: application/json' \
  -d '{"source":"avby"}'
docker compose exec -T db psql -U scrape -d scrape \
  -c "SELECT source, count(*) FROM listings GROUP BY 1"
```

Default job filters: `year_min=2010`, `price_usd_min=10000`, `max_hp=160`, `creation_date=10`, `pages=30`, interval ~25 min.

## Auto160 import

```bash
cd ~/auto160/backend
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_avby_scrape_listings.py --dry-run --limit 20

docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_avby_scrape_listings.py
```

Scheduled: `avby-sync` → `schedule_avby_listings_sync.py` → scrape DSN importer (no direct crawl of `web-api.av.by` for listings).

Legacy HTTP crawler `tools/import_avby_listings.py` remains for helpers / business-org tooling; do not use it for the main sync loop.

## Cutover checklist

1. Scrape: `avby` run succeeds → rows in `listings` with photos.
2. Auto160: one importer run → `car_listings` with `avby_id` and `/media/object?key=avby/…` covers.
3. `avby-sync` logs show DSN import only (no `fetch-brand: Audi…`).
