"""Collect av.by ocenka / price-statistics for catalog generations.

Default: rating=1 generations.
With --makes: all catalog generations for those brands (e.g. peugeot,renault).

Designed for careful production runs:
- adaptive delays + jitter
- resume-friendly (skips already-ok year rows)
- stops after consecutive hard failures / rate-limit storms
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from sqlalchemy import or_  # noqa: E402

from app.avby_price_stats import (  # noqa: E402
    SoftRateLimit,
    AvbyPriceStatsClient,
    build_catalog_generation_rows,
    fetch_and_store_year_stat,
    resolve_target,
    upsert_targets_from_catalog,
    years_for_target,
)
from app.db import SessionLocal  # noqa: E402
from app.models import AvbyPriceStatTarget, AvbyPriceYearStat  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collect_avby_price_stats")


def _parse_makes(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    makes = [part.strip() for part in raw.split(",") if part.strip()]
    return makes or None


def _progress(db, *, makes: list[str] | None = None) -> dict[str, int]:
    def _targets():
        q = db.query(AvbyPriceStatTarget)
        if makes:
            q = q.filter(or_(*[AvbyPriceStatTarget.make.ilike(m) for m in makes]))
        return q

    def _years():
        q = db.query(AvbyPriceYearStat)
        if makes:
            q = q.join(AvbyPriceStatTarget).filter(
                or_(*[AvbyPriceStatTarget.make.ilike(m) for m in makes])
            )
        return q

    return {
        "targets": _targets().count(),
        "ready": _targets().filter(AvbyPriceStatTarget.resolve_status == "ready").count(),
        "pending": _targets().filter(AvbyPriceStatTarget.resolve_status == "pending").count(),
        "failed_resolve": _targets()
        .filter(AvbyPriceStatTarget.resolve_status == "error")
        .count(),
        "year_ok": _years().filter(AvbyPriceYearStat.fetch_status == "ok").count(),
        "year_err": _years().filter(AvbyPriceYearStat.fetch_status == "error").count(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Only upsert targets and print plan")
    parser.add_argument("--limit-targets", type=int, default=None)
    parser.add_argument("--limit-years", type=int, default=None, help="Max year-stat fetches this run")
    parser.add_argument("--min-delay", type=float, default=5.0)
    parser.add_argument("--max-delay", type=float, default=9.0)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch year rows that are already ok")
    parser.add_argument("--skip-active", action="store_true", help="Skip active-adverts endpoint (fewer requests)")
    parser.add_argument("--resolve-only", action="store_true", help="Only resolve landing IDs")
    parser.add_argument("--slug", type=str, default=None, help="Process a single catalog slug")
    parser.add_argument(
        "--makes",
        type=str,
        default=None,
        help="Comma-separated makes; upserts ALL generations for them (e.g. peugeot,renault)",
    )
    parser.add_argument(
        "--arbitrage-track",
        action="store_true",
        help="Only generations marked «Аналитика РБ» (arbitrage_track)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=None,
        help="Skip years before this (reduces volume for full-brand dumps)",
    )
    parser.add_argument(
        "--max-year",
        type=int,
        default=None,
        help="Skip years after this",
    )
    parser.add_argument("--max-consecutive-errors", type=int, default=8)
    parser.add_argument("--pause-every", type=int, default=25, help="Extra pause after N successful year fetches")
    parser.add_argument("--pause-seconds", type=float, default=45.0)
    args = parser.parse_args()
    makes = _parse_makes(args.makes)

    rate = SoftRateLimit(min_delay=args.min_delay, max_delay=args.max_delay)
    client = AvbyPriceStatsClient(rate=rate)
    db = SessionLocal()
    started = time.time()
    try:
        created = upsert_targets_from_catalog(
            db,
            makes=makes,
            arbitrage_track_only=args.arbitrage_track,
        )
        scope = (
            f"arbitrage_track makes={makes}"
            if args.arbitrage_track and makes
            else ("arbitrage_track" if args.arbitrage_track else (makes or "rating=1"))
        )
        logger.info(
            "targets upserted; newly_created=%s scope=%s progress=%s",
            created,
            scope,
            _progress(db, makes=makes),
        )

        q = db.query(AvbyPriceStatTarget).order_by(
            AvbyPriceStatTarget.make.asc(),
            AvbyPriceStatTarget.model.asc(),
            AvbyPriceStatTarget.id.asc(),
        )
        if args.slug:
            q = q.filter(AvbyPriceStatTarget.catalog_slug == args.slug)
        if args.arbitrage_track:
            tracked_slugs = [
                r["catalog_slug"]
                for r in build_catalog_generation_rows(
                    db,
                    makes=makes,
                    rating_one_only=False,
                    arbitrage_track_only=True,
                )
            ]
            if not tracked_slugs:
                logger.warning("no arbitrage_track generations matched; nothing to do")
                return
            q = q.filter(AvbyPriceStatTarget.catalog_slug.in_(tracked_slugs))
        elif makes:
            q = q.filter(or_(*[AvbyPriceStatTarget.make.ilike(m) for m in makes]))
        targets = q.all()
        if args.limit_targets is not None:
            targets = targets[: args.limit_targets]

        year_kwargs = {"min_year": args.min_year, "max_year": args.max_year}
        year_plan = 0
        for t in targets:
            year_plan += len(years_for_target(t, **year_kwargs))
        logger.info(
            "plan targets=%s year_calls~=%s include_active=%s dry_run=%s min_year=%s",
            len(targets),
            year_plan,
            not args.skip_active,
            args.dry_run,
            args.min_year,
        )
        if args.dry_run:
            for t in targets[:20]:
                ys = years_for_target(t, **year_kwargs)
                logger.info(
                    "  %s | %s %s %s | years=%s-%s (%s) | status=%s",
                    t.catalog_slug,
                    t.make,
                    t.model,
                    t.generation or "",
                    ys[0] if ys else None,
                    ys[-1] if ys else None,
                    len(ys),
                    t.resolve_status,
                )
            if len(targets) > 20:
                logger.info("  ... and %s more", len(targets) - 20)
            return

        consecutive_errors = 0
        resolved = 0
        fetched = 0
        skipped = 0
        errors = 0

        for idx, target in enumerate(targets, start=1):
            if target.resolve_status != "ready" or not target.generation_id:
                try:
                    resolve_target(client, target)
                    db.commit()
                    resolved += 1
                    consecutive_errors = 0
                    logger.info(
                        "[%s/%s] resolved %s -> brand=%s model=%s gen=%s",
                        idx,
                        len(targets),
                        target.catalog_slug,
                        target.brand_id,
                        target.model_id,
                        target.generation_id,
                    )
                except Exception as exc:
                    target.resolve_status = "error"
                    target.resolve_error = str(exc)[:2000]
                    target.updated_at = datetime.utcnow()
                    db.commit()
                    consecutive_errors += 1
                    errors += 1
                    logger.warning(
                        "[%s/%s] resolve-fail %s: %s",
                        idx,
                        len(targets),
                        target.catalog_slug,
                        exc,
                    )
                    if consecutive_errors >= args.max_consecutive_errors:
                        logger.error("stopping: consecutive errors=%s", consecutive_errors)
                        break
                    continue

            if args.resolve_only:
                continue

            years = years_for_target(target, **year_kwargs)
            if not years:
                logger.warning("no years for %s", target.catalog_slug)
                continue

            for year in years:
                if args.limit_years is not None and fetched >= args.limit_years:
                    logger.info("limit-years reached (%s); stopping", args.limit_years)
                    logger.info(
                        "done resolved=%s fetched=%s skipped=%s errors=%s elapsed=%.0fs progress=%s",
                        resolved,
                        fetched,
                        skipped,
                        errors,
                        time.time() - started,
                        _progress(db, makes=makes),
                    )
                    return

                if not args.refresh:
                    existing = (
                        db.query(AvbyPriceYearStat)
                        .filter(
                            AvbyPriceYearStat.brand_id == target.brand_id,
                            AvbyPriceYearStat.model_id == target.model_id,
                            AvbyPriceYearStat.generation_id == target.generation_id,
                            AvbyPriceYearStat.year == year,
                            AvbyPriceYearStat.fetch_status == "ok",
                        )
                        .first()
                    )
                    if existing is not None:
                        skipped += 1
                        continue

                try:
                    row = fetch_and_store_year_stat(
                        db,
                        client,
                        target,
                        year,
                        include_active=not args.skip_active,
                        refresh=args.refresh,
                    )
                    fetched += 1
                    consecutive_errors = 0
                    logger.info(
                        "[%s/%s] year=%s ok price_usd=%s adverts=%s active=%s slug=%s",
                        idx,
                        len(targets),
                        year,
                        row.price_usd,
                        row.advert_count,
                        row.active_advert_count,
                        target.catalog_slug,
                    )
                    if args.pause_every > 0 and fetched % args.pause_every == 0:
                        logger.info(
                            "cool-down pause %.0fs after %s fetches (WAF hygiene)",
                            args.pause_seconds,
                            fetched,
                        )
                        time.sleep(args.pause_seconds)
                except Exception as exc:
                    errors += 1
                    consecutive_errors += 1
                    err_row = (
                        db.query(AvbyPriceYearStat)
                        .filter(
                            AvbyPriceYearStat.brand_id == target.brand_id,
                            AvbyPriceYearStat.model_id == target.model_id,
                            AvbyPriceYearStat.generation_id == target.generation_id,
                            AvbyPriceYearStat.year == year,
                        )
                        .first()
                    )
                    if err_row is None:
                        err_row = AvbyPriceYearStat(
                            target_id=target.id,
                            brand_id=int(target.brand_id or 0),
                            model_id=int(target.model_id or 0),
                            generation_id=int(target.generation_id or 0),
                            year=year,
                        )
                        db.add(err_row)
                    err_row.fetch_status = "error"
                    err_row.fetch_error = str(exc)[:2000]
                    err_row.fetched_at = datetime.utcnow()
                    db.commit()
                    logger.warning(
                        "[%s/%s] year=%s fail slug=%s: %s",
                        idx,
                        len(targets),
                        year,
                        target.catalog_slug,
                        exc,
                    )
                    if consecutive_errors >= args.max_consecutive_errors:
                        logger.error("stopping: consecutive errors=%s", consecutive_errors)
                        logger.info(
                            "done resolved=%s fetched=%s skipped=%s errors=%s elapsed=%.0fs progress=%s",
                            resolved,
                            fetched,
                            skipped,
                            errors,
                            time.time() - started,
                            _progress(db, makes=makes),
                        )
                        return

        logger.info(
            "done resolved=%s fetched=%s skipped=%s errors=%s elapsed=%.0fs progress=%s",
            resolved,
            fetched,
            skipped,
            errors,
            time.time() - started,
            _progress(db, makes=makes),
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
