"""One-off: sync account counter when av.by paywall error is already stored."""

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
    mark_vin_daily_limit_exhausted,
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
        mark_vin_daily_limit_exhausted(db, acc, error_message=acc.error_message)
        print(f"synced {email}: {acc.vin_checks_today}/{acc.daily_vin_limit}, remaining={vin_checks_remaining(acc)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
