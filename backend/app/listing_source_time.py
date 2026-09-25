"""Helpers for feed ordering timestamps on multi-source listings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

# If scrape first_seen is this much older than local created_at, treat it as a
# bulk-seed artifact (common for early autoplius rows) and prefer created_at.
_BULK_SEED_SLACK = timedelta(hours=12)


def _as_naive_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value
    return None


def scrape_source_timestamps(row: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """Return (published_at, renewed_at) from scrape-platform listing row.

    Scrape DB has ``first_seen_at`` / ``last_seen_at`` / ``updated_at`` (no created_at).
    Prefer ``first_seen_at`` for appearance order. Avoid ``updated_at``: it often marks
    whole scrape batches and re-clusters the Europe feed by country.
    """
    published = _as_naive_utc(row.get("first_seen_at") or row.get("created_at"))
    renewed = published
    return published, renewed


def _prefer_local_created(listing: Any, scrape_ts: datetime | None) -> datetime | None:
    """Fall back to local created_at when scrape first_seen looks like a bulk seed."""
    created = _as_naive_utc(getattr(listing, "created_at", None))
    if scrape_ts is None:
        return created
    if created is not None and scrape_ts < (created - _BULK_SEED_SLACK):
        return created
    return scrape_ts


def apply_scrape_source_timestamps(listing: Any, row: dict[str, Any]) -> None:
    """Store scrape times on CarListing avby_* timestamp columns used by feed sort.

    Call again after flush on newly created rows so ``created_at`` can correct bulk seeds.
    """
    published, renewed = scrape_source_timestamps(row)
    published = _prefer_local_created(listing, published)
    renewed = _prefer_local_created(listing, renewed)
    if published is not None:
        listing.avby_published_at = published
    if renewed is not None:
        listing.avby_renewed_at = renewed
