#!/usr/bin/env python3
"""Dry-run Autoplius scrape DB → Auto160 listing mapping (no writes).

Example (from VM api container):

  python tools/dry_run_autoplius_import.py --limit 0
  python tools/dry_run_autoplius_import.py --limit 20 --samples 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import psycopg2
import psycopg2.extras

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.autoplius_map import fetch_eur_rate, map_autoplius_row

DEFAULT_DSN = "postgresql://scrape:scrape@10.129.0.33:5433/scrape"
DEFAULT_MEDIA_BASE = "http://10.129.0.33:8000"

SELECT_SQL = """
SELECT
  id,
  source,
  external_id,
  url,
  title,
  year,
  body_type,
  price_eur,
  fuel,
  transmission,
  engine_liters,
  mileage_km,
  city,
  photo_url,
  photo_urls,
  description,
  description_ru,
  phone,
  vin_masked,
  parameters,
  raw,
  detail_scraped,
  status
FROM listings
WHERE source = %s AND status = %s
ORDER BY id DESC
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run Autoplius → Auto160 mapping")
    parser.add_argument("--dsn", default=os.getenv("AUTOPLIUS_SCRAPE_DSN", DEFAULT_DSN))
    parser.add_argument("--media-base", default=os.getenv("AUTOPLIUS_MEDIA_BASE", DEFAULT_MEDIA_BASE))
    parser.add_argument("--source", default="autoplius")
    parser.add_argument("--status", default="active")
    parser.add_argument("--limit", type=int, default=0, help="0 = all matching rows")
    parser.add_argument("--max-hp", type=int, default=160)
    parser.add_argument("--allow-missing-hp", action="store_true")
    parser.add_argument("--include-undetailed", action="store_true")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--json-out", default="", help="Optional path for full mapped JSONL")
    args = parser.parse_args()

    max_hp = None if args.allow_missing_hp and args.max_hp <= 0 else args.max_hp
    eur = fetch_eur_rate()
    if eur:
        print(f"nbrb_eur rate={eur.rate} scale={eur.scale} date={eur.rate_date.isoformat()}")
    else:
        print("nbrb_eur UNAVAILABLE (price_byn will be null)")

    conn = psycopg2.connect(args.dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            sql = SELECT_SQL
            params: list = [args.source, args.status]
            if args.limit and args.limit > 0:
                sql += " LIMIT %s"
                params.append(args.limit)
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    print(f"fetched={len(rows)} source={args.source} status={args.status}")

    skips: Counter[str] = Counter()
    ok = 0
    samples_ok: list[dict] = []
    samples_skip: list[dict] = []
    json_out = open(args.json_out, "w", encoding="utf-8") if args.json_out else None
    try:
        for row in rows:
            mapped = map_autoplius_row(
                dict(row),
                eur_rate=eur,
                media_base=args.media_base,
                max_hp=max_hp,
                require_detail=not args.include_undetailed,
            )
            payload = mapped.to_dict()
            if json_out is not None:
                json_out.write(json.dumps(payload, ensure_ascii=False) + "\n")
            if mapped.skip_reason:
                skips[mapped.skip_reason] += 1
                if len(samples_skip) < args.samples:
                    samples_skip.append(payload)
            else:
                ok += 1
                if len(samples_ok) < args.samples:
                    samples_ok.append(payload)
    finally:
        if json_out is not None:
            json_out.close()

    print(f"would_import={ok}")
    print("skip_reasons:")
    for reason, count in skips.most_common():
        print(f"  {reason}: {count}")

    print("\n=== sample OK ===")
    for item in samples_ok:
        print(
            json.dumps(
                {
                    "external_id": item["external_id"],
                    "brand": item["brand"],
                    "model": item["model"],
                    "year": item["year"],
                    "hp": item["engine_power_hp"],
                    "price_eur": item["price_eur"],
                    "price_byn": item["price_byn"],
                    "city": item["city"],
                    "photos": len(item["photo_urls"]),
                    "url": item["source_url"],
                },
                ensure_ascii=False,
            )
        )

    print("\n=== sample SKIP ===")
    for item in samples_skip:
        print(
            json.dumps(
                {
                    "skip_reason": item["skip_reason"],
                    "external_id": item["external_id"],
                    "title": item["title"],
                    "brand": item["brand"],
                    "model": item["model"],
                    "year": item["year"],
                    "hp": item["engine_power_hp"],
                    "price_eur": item["price_eur"],
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
