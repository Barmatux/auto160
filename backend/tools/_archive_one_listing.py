import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.avby_offer_check import check_avby_offer_public
from app.db import SessionLocal
from app.models import CarListing, ListingStatus

avby_id = int(sys.argv[1])
db = SessionLocal()
r = db.query(CarListing).filter(CarListing.avby_id == avby_id).first()
if not r:
    print("not found")
    raise SystemExit(1)
print("before", r.id, r.status.value, float(r.price))
result = check_avby_offer_public(avby_id, r.source_url)
print("check", result.value)
if result.value == "removed":
    r.status = ListingStatus.archived
    db.commit()
    print("after", r.status.value)
else:
    print("unchanged")
db.close()
