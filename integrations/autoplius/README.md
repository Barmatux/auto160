# Autoplius (Lithuania) listings → Auto160

## What it does

- Imports active Autoplius ads (≤160 hp) from scrape Postgres into `car_listings`
- Photos served via `/media/autoplius?key=...` from Yandex bucket `autoplius-media`
- UI tab: **Литва** → `/listings/lt` (Belarus feed stays `/listings`)

## Env (VM `.env.vm`)

```bash
AUTOPLIUS_SCRAPE_DSN=postgresql://scrape:scrape@10.129.0.33:5433/scrape
AUTOPLIUS_S3_ENDPOINT_URL=https://storage.yandexcloud.net
AUTOPLIUS_S3_ACCESS_KEY=...
AUTOPLIUS_S3_SECRET_KEY=...
AUTOPLIUS_S3_BUCKET=autoplius-media
AUTOPLIUS_S3_REGION=ru-central1
```

## Commands

```bash
cd ~/auto160/backend
# dry-run mapping
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/dry_run_autoplius_import.py --limit 0 --samples 5

# import (after migration 0024)
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_autoplius_listings.py --limit 50

# full import
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_autoplius_listings.py
```

Identity: `source=autoplius` + `external_id`. Belarus av.by rows use `source=av.by`.
