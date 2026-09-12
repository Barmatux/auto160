#!/usr/bin/env python3
"""Recompute listing_avg_prices (brand/model/year) for 30/60/90-day windows.

Usage:
  python tools/recompute_listing_avg_prices.py
  python tools/recompute_listing_avg_prices.py --windows 30,60,90 --min-samples 11
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import SessionLocal
from app.listing_avg_prices import (
    DEFAULT_MIN_SAMPLES,
    DEFAULT_WINDOWS,
    recompute_listing_avg_prices,
)


def _parse_windows(raw: str) -> tuple[int, ...]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    if not parts:
        return DEFAULT_WINDOWS
    return tuple(sorted({max(1, int(p)) for p in parts}))


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute brand/model/year average BYN prices")
    parser.add_argument(
        "--windows",
        default=",".join(str(d) for d in DEFAULT_WINDOWS),
        help="Comma-separated rolling windows in days (default: 30,60,90)",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=None,
        help="Legacy single-window override (ignored if --windows is used as default set)",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=DEFAULT_MIN_SAMPLES,
        help="Minimum listings after outlier trim to store a row (default: 11 = >10)",
    )
    parser.add_argument(
        "--no-trim-outliers",
        action="store_true",
        help="Disable Tukey IQR outlier removal",
    )
    args = parser.parse_args()

    windows = (max(1, args.window_days),) if args.window_days is not None else _parse_windows(args.windows)

    db = SessionLocal()
    try:
        stats = recompute_listing_avg_prices(
            db,
            windows=windows,
            min_samples=args.min_samples,
            trim_outliers=not args.no_trim_outliers,
        )
    finally:
        db.close()

    print(
        "avg-prices: "
        f"windows={list(stats.window_days)} scanned={stats.listings_scanned} "
        f"groups={stats.groups} written={stats.rows_written} "
        f"from={stats.window_start.isoformat()} to={stats.window_end.isoformat()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
