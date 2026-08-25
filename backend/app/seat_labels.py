"""Seat-count helpers for catalog filters (av.by numberOfSeats)."""

from __future__ import annotations

import re

_SEAT_TOKEN_RE = re.compile(r"\d+")


def normalize_seats_raw(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).replace("\xa0", " ").strip()
    return cleaned or None


def parse_seat_counts(value: str | None) -> set[int]:
    raw = normalize_seats_raw(value)
    if not raw:
        return set()
    return {int(token) for token in _SEAT_TOKEN_RE.findall(raw)}


def seats_include_count(value: str | None, seat: int) -> bool:
    return seat in parse_seat_counts(value)


def seats_raw_from_specs(raw_specs: dict | None) -> str | None:
    if not isinstance(raw_specs, dict):
        return None
    detail = raw_specs.get("modification_detail")
    if isinstance(detail, dict):
        return normalize_seats_raw(detail.get("numberOfSeats"))
    return None


def has_7_seats_from_raw(value: str | None = None, *, raw_specs: dict | None = None) -> bool:
    seats = normalize_seats_raw(value)
    if seats is None:
        seats = seats_raw_from_specs(raw_specs)
    return seats_include_count(seats, 7)
