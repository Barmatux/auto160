"""Persist per-listing VIN check results for av.by sync runs."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AvbySyncRunVinCheck, CarListing

PHASE_METADATA = "metadata"
PHASE_RATING1 = "rating1"

PHASE_LABELS = {
    PHASE_METADATA: "Метаданные av.by",
    PHASE_RATING1: "Rating 1 (VIN + таможня)",
}


def record_sync_run_vin_check(
    db: Session,
    *,
    sync_run_id: int,
    listing: CarListing,
    phase: str,
    vin_obtained: bool,
    vin: str | None = None,
    vin_indicated: bool | None = None,
    customs_checked: bool = False,
    customs_found: bool | None = None,
    error_message: str | None = None,
) -> AvbySyncRunVinCheck:
    row = AvbySyncRunVinCheck(
        sync_run_id=sync_run_id,
        listing_id=listing.id,
        phase=phase,
        vin_obtained=vin_obtained,
        vin=(vin or listing.vin or "").strip().upper() or None,
        vin_indicated=vin_indicated,
        customs_checked=customs_checked,
        customs_found=customs_found,
        error_message=(error_message[:500] if error_message else None),
    )
    db.add(row)
    return row


def summarize_sync_run_vin_checks(rows: list[AvbySyncRunVinCheck]) -> dict[str, int]:
    checked = len(rows)
    vin_obtained = sum(1 for row in rows if row.vin_obtained)
    customs_checked = sum(1 for row in rows if row.customs_checked)
    customs_found = sum(1 for row in rows if row.customs_found is True)
    return {
        "checked": checked,
        "vin_obtained": vin_obtained,
        "customs_checked": customs_checked,
        "customs_found": customs_found,
    }
