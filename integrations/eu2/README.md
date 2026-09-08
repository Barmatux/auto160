"""Wire-up notes for eu2.by ↔ auto160 catalog match.

## auto160 side

1. Set in `backend/.env.vm`:
   - `INTERNAL_CATALOG_API_KEY=<long random>`
   - optional `INTERNAL_CATALOG_ALLOWED_IPS=...`
2. Run migration `0021_catalog_gaps`.
3. Apply nginx (`scripts/nginx-auto160.conf`) so `/api/v1/internal/` is only reachable from private nets.
4. Restart API.

## eu2 side

1. Copy `auto160_catalog_client.py` into the eu2 codebase.
2. Set env:
   - `AUTO160_CATALOG_BASE_URL=http://127.0.0.1:8000` (or private IP of auto160)
   - `AUTO160_CATALOG_API_KEY=<same key>`
3. After each successful parse, build unique modification-level candidates and call:

```python
from auto160_catalog_client import CatalogCandidate, reconcile_after_parse

def after_parse(parsed_mods):
    candidates = [
        CatalogCandidate(
            external_ref=str(mod.id),
            make=mod.make,
            model=mod.model,
            generation=mod.generation,
            year=mod.year,
            body_type=mod.body_type,
            fuel_type=mod.fuel_type,
            engine_power_hp=mod.hp,
            source_external_id=mod.avby_id,
        )
        for mod in unique_modifications(parsed_mods)
    ]

    def save_link(result):
        # UPDATE eu2_entity SET catalog_item_id = result.matched_catalog_item_id
        # WHERE id = result.external_ref
        ...

    def log_gap(result):
        # local log; auto160 also stores catalog_gaps when enqueue_gaps=True
        ...

    reconcile_after_parse(candidates, on_matched=save_link, on_not_found=log_gap)
```

Keep parse persistence and catalog reconcile as separate steps so a temporary auto160 outage does not lose ads (client retries 3x).
