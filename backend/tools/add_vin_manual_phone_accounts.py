"""Add phone-based av.by accounts for manual VIN checks (excluded from parser rotation).

Example (do not commit passwords):
  python tools/add_vin_manual_phone_accounts.py \\
    --account 295121829:Qwerty2012 \\
    --account 292903719:Qwerty2026 \\
    --account 292975498:Qwerty2026

Accounts are saved as purpose=vin_test with is_active=False so they stay out of
automatic parser / enrichment rotation, but remain usable for admin VIN checks.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import VIN_TEST_DAILY_LIMIT, normalize_avby_phone, upsert_avby_service_account
from app.avby_session import AvbySessionError, get_avby_session
from app.db import SessionLocal


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_account(raw: str) -> tuple[str, str]:
    text = (raw or "").strip()
    if ":" not in text:
        raise SystemExit(f"Expected phone:password, got {raw!r}")
    phone_raw, password = text.split(":", 1)
    phone = normalize_avby_phone(phone_raw)
    if not phone:
        raise SystemExit(f"Invalid phone: {phone_raw!r}")
    if not password.strip():
        raise SystemExit(f"Empty password for phone {phone}")
    return phone, password.strip()


def add_account(db, *, phone: str, password: str, login: bool) -> None:
    payload = {
        "phone": phone,
        "avby_password": password,
        "name": f"VIN manual +375{phone}",
        "purpose": "vin_test",
        "daily_vin_limit": VIN_TEST_DAILY_LIMIT,
        "vin_checks_today": 0,
        "is_active": False,
        "status": "phone_verified",
        "notes": (
            "manual VIN validation only; excluded from parser/auto rotation "
            f"(is_active=false); added {_utc_now()}"
        ),
        "created_at": _utc_now(),
    }
    row = upsert_avby_service_account(db, payload)
    row.purpose = "vin_test"
    row.is_active = False
    row.daily_vin_limit = row.daily_vin_limit or VIN_TEST_DAILY_LIMIT
    db.commit()
    db.refresh(row)

    if not login:
        print(f"saved id={row.id} phone=+375{phone} is_active={row.is_active} (no login)")
        return

    try:
        session = get_avby_session(db, row, allow_captcha=True)
        row.error_message = None
        row.is_active = False  # never enable auto rotation for these
        if row.status not in {"phone_verified", "confirmed"}:
            row.status = "confirmed"
        db.commit()
        db.refresh(row)
        print(
            f"OK id={row.id} phone=+375{phone} status={row.status} "
            f"is_active={row.is_active} api_key={bool(row.api_key)} "
            f"expires={session.expires_at.isoformat()}Z"
        )
    except AvbySessionError as exc:
        row.is_active = False
        row.error_message = str(exc)[:500]
        db.commit()
        print(f"FAIL id={row.id} phone=+375{phone}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add vin_test phone accounts outside parser rotation")
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="phone:password (9-digit BY phone or +375…)",
    )
    parser.add_argument("--no-login", action="store_true", help="Only save credentials, skip av.by login/captcha")
    args = parser.parse_args()
    if not args.account:
        raise SystemExit("Pass at least one --account phone:password")

    pairs = [_parse_account(item) for item in args.account]
    db = SessionLocal()
    try:
        for phone, password in pairs:
            add_account(db, phone=phone, password=password, login=not args.no_login)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
