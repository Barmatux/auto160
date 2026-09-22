# Auto24 (Estonia) listings → Auto160

## What it does

- Imports active Auto24 ads (≤160 hp, age ≤5 years, engine ≤1.9 L) from scrape Postgres into `car_listings`
- Photos: prefer CDN URLs from scrape `parameters.source_photo_urls` (Yandex `auto24/` keys are often missing until scrape uploads them)
- UI tab: **Эстония** → `/listings/ee`

## Env

Uses the same scrape DSN / media bucket as Autoplius (`AUTOPLIUS_SCRAPE_DSN`, `AUTOPLIUS_S3_*`).

## Commands

```bash
cd ~/auto160/backend
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_auto24_listings.py --dry-run

docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_auto24_listings.py
```

## Scheduled sync (VM)

`auto24-sync` every 45 minutes (no daytime embeddings). Mapping reads `engine` as `{liters} {kW}kW` and converts kW→hp.

Identity: `source=auto24` + `external_id`.
