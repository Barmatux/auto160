"""Import personal av.by account as VIN test account (30 checks/day).

Credentials: data/avby_vin_test_credentials.json (gitignored) or env:
  AVBY_VIN_TEST_EMAIL, AVBY_VIN_TEST_PASSWORD

On VM:
  docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \\
    python tools/import_avby_vin_test_account.py
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import VIN_TEST_DAILY_LIMIT, upsert_avby_service_account
from app.db import SessionLocal
from tools.register_avby_accounts import _captcha_env_api_key, solve_recaptcha_invisible
from tools.verify_avby_phone import AvbyClient

# Public key from av.by frontend (same for all users until login returns personal api_key in JWT).
AVBY_PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"

CREDENTIALS_PATH = Path("data/avby_vin_test_credentials.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}


def load_credentials() -> tuple[str, str]:
    email = (os.environ.get("AVBY_VIN_TEST_EMAIL") or "").strip()
    password = os.environ.get("AVBY_VIN_TEST_PASSWORD") or ""

    if CREDENTIALS_PATH.exists():
        raw = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        email = email or (raw.get("email") or "").strip()
        password = password or (raw.get("password") or "")

    if not email or not password:
        raise SystemExit(
            f"Set AVBY_VIN_TEST_EMAIL/PASSWORD or create {CREDENTIALS_PATH} "
            'with {"email":"...","password":"..."}'
        )
    return email, password


def login_account(email: str, password: str) -> AvbyClient:
    captcha_token = ""
    captcha_api_key = _captcha_env_api_key()
    if captcha_api_key:
        print("Solving av.by login reCAPTCHA via 2captcha...")
        captcha_token = solve_recaptcha_invisible(api_key=captcha_api_key, page_url="https://av.by/")
    avby = AvbyClient(AVBY_PUBLIC_API_KEY)
    login_data = avby.login(email, password, captcha_token=captcha_token)
    print("login ok, user id:", (login_data.get("user") or {}).get("id"))
    jwt_api_key = _decode_jwt_payload(avby.token or "").get("api_key")
    if jwt_api_key:
        avby.api_key = jwt_api_key
    return avby


def main() -> int:
    parser = argparse.ArgumentParser(description="Import av.by VIN test account into DB")
    parser.add_argument("--email", help="Override email")
    parser.add_argument("--password", help="Override password (avoid in shell history)")
    args = parser.parse_args()

    email, password = load_credentials()
    if args.email:
        email = args.email.strip()
    if args.password:
        password = args.password

    account = {
        "email": email,
        "avby_password": password,
        "name": "",
        "purpose": "vin_test",
        "daily_vin_limit": VIN_TEST_DAILY_LIMIT,
        "vin_checks_today": 0,
        "is_active": False,
        "created_at": _utc_now(),
    }

    avby = login_account(email, password)
    api_key = avby.api_key
    if not api_key:
        raise SystemExit("Login ok but api_key missing from JWT")

    me = avby.me()
    phone_verified = bool(me.get("isPhoneVerified"))
    account.update(
        {
            "name": (me.get("name") or me.get("firstName") or "VIN Test")[:120],
            "api_key": api_key,
            "auth_token": avby.token,
            "refresh_token": avby.refresh_token,
            "status": "phone_verified" if phone_verified else "confirmed",
            "is_active": phone_verified,
            "notes": (
                f"personal vin_test account; daily_vin_limit={VIN_TEST_DAILY_LIMIT}; "
                f"phone_verified={phone_verified}; user_id={me.get('id')}"
            ),
        }
    )

    db = SessionLocal()
    try:
        row = upsert_avby_service_account(db, account)
        from app.avby_session import get_avby_session

        session = get_avby_session(db, row)
        print(f"session warmed until {session.expires_at.isoformat()} UTC")
    finally:
        db.close()

    out = {**account, "is_phone_verified": phone_verified}
    out.pop("avby_password", None)
    Path("data/avby_vin_test_account.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("=== VIN test account imported ===")
    print(f"email:           {row.email}")
    print(f"status:          {row.status}")
    print(f"phone verified:  {phone_verified}")
    print(f"daily limit:     {row.daily_vin_limit}")
    print(f"is_active:       {row.is_active}")
    if not phone_verified:
        print("\nPhone not verified — VIN API will return require_phone_verification.")
        print("Verify manually or run verify_avby_phone.py --manual-phone ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
