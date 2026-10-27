"""Exact engine displacement (cm³) for catalog items."""

from __future__ import annotations

import re
from typing import Any

# av.by stores engineCapacity as "999 см.куб." / "1598" / "1 598 см³"
_CC_RE = re.compile(r"(\d[\d\s]*)")


def parse_engine_capacity_cc(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _CC_RE.search(text)
    if not match:
        return None
    digits = re.sub(r"\s+", "", match.group(1))
    if not digits.isdigit():
        return None
    cc = int(digits)
    if cc <= 0 or cc > 20000:
        return None
    return cc


def engine_capacity_cc_from_raw_specs(raw_specs: dict | None) -> int | None:
    if not isinstance(raw_specs, dict):
        return None
    detail = raw_specs.get("modification_detail")
    if not isinstance(detail, dict):
        return None
    return parse_engine_capacity_cc(detail.get("engineCapacity"))


def engine_capacity_cc_from_liters(volume_l: Any) -> int | None:
    if volume_l is None:
        return None
    try:
        liters = float(volume_l)
    except (TypeError, ValueError):
        return None
    if liters <= 0:
        return None
    return int(round(liters * 1000))


def resolve_engine_capacity_cc(
    *,
    engine_capacity_cc: int | None = None,
    raw_specs: dict | None = None,
    engine_volume_l: Any = None,
) -> int | None:
    if engine_capacity_cc is not None:
        try:
            cc = int(engine_capacity_cc)
        except (TypeError, ValueError):
            cc = None
        else:
            if 0 < cc <= 20000:
                return cc
    parsed = engine_capacity_cc_from_raw_specs(raw_specs)
    if parsed is not None:
        return parsed
    return engine_capacity_cc_from_liters(engine_volume_l)
