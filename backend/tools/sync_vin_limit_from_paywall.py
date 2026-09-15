"""One-off: attach paywall error note without faking the local VIN counter."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import (
    is_avby_vin_daily_limit_error_message,
    note_vin_paywall_error,
    vin_checks_remaining,
)
from app.db import SessionLocal
from app.models import AvbyServiceAccount


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    email = sys.argv[1] if len(sys.argv) > 1 else "kupi1kupi@gmail.com"
    db = SessionLocal()
    try:
        acc = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == email).first()
        if not acc:
            raise SystemExit(f"Account not found: {email}")
        if not is_avby_vin_daily_limit_error_message(acc.error_message):
            print(f"skip: no paywall error on {email!r}")
            return
        note_vin_paywall_error(db, acc, error_message=acc.error_message)
        print(
            f"noted paywall on {email}: counter unchanged "
            f"{acc.vin_checks_today}/{acc.daily_vin_limit}, remaining={vin_checks_remaining(acc)}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
