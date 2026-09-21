# Listing embeddings (pgvector)

Published `car_listings` are embedded into Postgres (`listing_embeddings`) for semantic search.

## Env (VM `.env.vm`)

```bash
OPENAI_API_KEY=sk-or-v1-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
# Required from Yandex Cloud VMs (OpenRouter blocks those IPs without a proxy):
OPENAI_HTTP_PROXY=http://user:pass@host:port
EMBEDDING_MODEL=openai/text-embedding-3-small
EMBEDDING_PROVIDER=openai
```

Without `OPENAI_API_KEY` the service uses deterministic **local hash vectors** so deploy/smoke works; set a real key and re-run `--force` for production quality.

## Backfill

```bash
cd ~/auto160/backend
docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \
  python tools/reindex_listing_embeddings.py
```

Options: `--limit 100`, `--force`, `--ids 1,2,3`.

After `avby-sync` / `autoplius-sync` the scheduler also runs reindex (skips unchanged `content_hash`). Without `OPENAI_API_KEY` sync continues; embeddings step logs a warning.

## API

```bash
curl 'http://127.0.0.1:8000/api/v1/listings/semantic?q=bmw+x1+автомат&limit=10'
```
