"""Helpers for feed ordering timestamps on multi-source listings."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any, Iterable

# Identical first_seen shared by this many scrape rows ⇒ treat as bulk seed, not appearance.
_BULK_FIRST_SEEN_MIN_COUNT = 30


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

    Prefer ``first_seen_at`` for appearance order. Avoid ``updated_at``: it often marks
    whole scrape batches and re-clusters the Europe feed by country.
    """
    published = _as_naive_utc(row.get("first_seen_at") or row.get("created_at"))
    renewed = published
    return published, renewed


def detect_bulk_first_seen(
    rows: Iterable[dict[str, Any]],
    *,
    min_count: int = _BULK_FIRST_SEEN_MIN_COUNT,
) -> set[tuple[str, datetime]]:
    """Return (source, first_seen) pairs that look like bulk-seed timestamps."""
    counts: Counter[tuple[str, datetime]] = Counter()
    for row in rows:
        source = (row.get("source") or "").strip()
        first = _as_naive_utc(row.get("first_seen_at") or row.get("created_at"))
        if not source or first is None:
            continue
        counts[(source, first)] += 1
    return {key for key, n in counts.items() if n >= min_count}


def apply_scrape_source_timestamps(
    listing: Any,
    row: dict[str, Any],
    *,
    bulk_first_seen: set[tuple[str, datetime]] | None = None,
) -> None:
    """Store scrape times on CarListing avby_* columns used by feed sort.

    When ``first_seen_at`` is a known bulk-seed timestamp, fall back to local
    ``created_at`` so those rows do not pile on one day and dominate country blocks.
    """
    published, renewed = scrape_source_timestamps(row)
    source = (getattr(listing, "source", None) or row.get("source") or "").strip()
    created = _as_naive_utc(getattr(listing, "created_at", None))
    if (
        bulk_first_seen is not None
        and published is not None
        and source
        and (source, published) in bulk_first_seen
        and created is not None
    ):
        published = created
        renewed = created
    if published is not None:
        listing.avby_published_at = published
    if renewed is not None:
        listing.avby_renewed_at = renewed
