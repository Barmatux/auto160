"""Helpers for feed ordering timestamps on multi-source listings."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


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
    ``updated_at``/``last_seen_at`` are often identical within a scrape batch, so they
    re-cluster the Europe feed by country. Use ``first_seen_at`` for both fields so
    feed order follows source appearance across auto24 / autoplius / mobile_de.
    """
    published = _as_naive_utc(row.get("first_seen_at") or row.get("created_at"))
    # Do not prefer updated_at: it tracks scrape jobs, not listing appearance.
    renewed = published
    return published, renewed


def apply_scrape_source_timestamps(listing: Any, row: dict[str, Any]) -> None:
    """Store scrape times on CarListing avby_* timestamp columns used by feed sort."""
    published, renewed = scrape_source_timestamps(row)
    if published is not None:
        listing.avby_published_at = published
    if renewed is not None:
        listing.avby_renewed_at = renewed
