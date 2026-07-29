from app.models import AvbySyncRunVinCheck
from app.sync_run_vin_log import PHASE_METADATA, PHASE_RATING1, summarize_sync_run_vin_checks


def test_summarize_sync_run_vin_checks():
    rows = [
        AvbySyncRunVinCheck(
            sync_run_id=1,
            listing_id=10,
            phase=PHASE_METADATA,
            vin_obtained=True,
            vin="WBA12345678901234",
        ),
        AvbySyncRunVinCheck(
            sync_run_id=1,
            listing_id=11,
            phase=PHASE_METADATA,
            vin_obtained=False,
        ),
        AvbySyncRunVinCheck(
            sync_run_id=1,
            listing_id=12,
            phase=PHASE_RATING1,
            vin_obtained=True,
            vin="WBA98765432109876",
            customs_checked=True,
            customs_found=True,
        ),
    ]
    summary = summarize_sync_run_vin_checks(rows)
    assert summary == {
        "checked": 3,
        "vin_obtained": 2,
        "customs_checked": 1,
        "customs_found": 1,
    }
