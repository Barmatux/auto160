"""One-off: add page=1 and re-encode PEEP lot_url values in bca_lots."""

from __future__ import annotations

from app.bca_admin import canonical_peep_lot_url, public_lot_url_ok
from app.db import SessionLocal
from app.models import BcaLot


def main() -> None:
    db = SessionLocal()
    try:
        updated = 0
        for lot in db.query(BcaLot).filter(BcaLot.lot_url.like("%SourceSystem=PEEP%")):
            if not public_lot_url_ok(lot.lot_url):
                continue
            fixed = canonical_peep_lot_url(lot.lot_url)
            if fixed != lot.lot_url:
                lot.lot_url = fixed
                updated += 1
        db.commit()
        print(f"updated={updated}")
    finally:
        db.close()


if __name__ == "__main__":
    main()