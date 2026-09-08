#!/usr/bin/env python3
"""Recompute listing_avg_prices (brand/model/year) from the last N months of ads.

Usage:
  python tools/recompute_listing_avg_prices.py
  python tools/recompute_listing_avg_prices.py --window-days 90
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.listing_avg_prices import DEFAULT_WINDOW_DAYS, recompute_listing_avg_prices


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute brand/model/year average BYN prices")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="Rolling window in days (default: 90 ≈ 3 months)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=1,
        help="Minimum listings required to store a row",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = recompute_listing_avg_prices(
            db,
            window_days=args.window_days,
            min_samples=args.min_samples,
        )
    finally:
        db.close()

    print(
        "avg-prices: "
        f"window_days={stats.window_days} scanned={stats.listings_scanned} "
        f"groups={stats.groups} written={stats.rows_written} "
        f"from={stats.window_start.isoformat()} to={stats.window_end.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
