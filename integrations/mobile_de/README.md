# mobile.de listings → Auto160

## What it does

- Imports active mobile.de ads (≤160 hp, age ≤5 years, engine ≤1.9 L) from scrape Postgres into `car_listings`
- Photos: scrape S3 keys under `mobile_de/…` via `/media/object` (`auto160-media`)
- UI tab: **Германия** → `/listings/de`

## Env

Uses the same scrape DSN / media bucket as Autoplius (`AUTOPLIUS_SCRAPE_DSN`, `AUTOPLIUS_S3_*` / app `S3_*`).

## Commands

```bash
cd ~/auto160/backend
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_mobile_de_listings.py --dry-run

docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/import_mobile_de_listings.py
```

## Scheduled sync (VM)

`mobile-de-sync` every 45 minutes (no daytime embeddings). Mapping parses German engine strings like `1.499 cm³, 103 kW (140 PS)`.

Identity: `source=mobile_de` + `external_id`.
