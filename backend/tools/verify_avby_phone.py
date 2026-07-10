"""Verify av.by service account phone via HeroSMS virtual number or manual SMS.

Usage:
  set HERO_SMS_API_KEY=...
  python tools/verify_avby_phone.py --email avby01_wcs75ojf@web-library.net --from-db

Manual phone (real +375, no virtual SMS service):
  python tools/verify_avby_phone.py --from-db --email YOU@EMAIL --manual-phone 291234567
  python tools/verify_avby_phone.py --from-db --email YOU@EMAIL --manual-phone 291234567 --sms-code 1234

On VM (reads HERO_SMS_API_KEY from .env.vm):
  docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \\
    python tools/verify_avby_phone.py --from-db --list-accounts
  docker compose --env-file .env.vm -f docker-compose.vm.yml exec -T api \\
    python tools/verify_avby_phone.py --from-db --email YOUR@EMAIL
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import upsert_avby_service_account
from app.db import SessionLocal
from app.models import AvbyServiceAccount
from tools.register_avby_accounts import _captcha_env_api_key, solve_recaptcha_invisible

AVBY_BASE = "https://web-api.av.by"
HERO_SMS_BASE = "https://hero-sms.com/stubs/handler_api.php"
HERO_SMS_COUNTRY_BY = 51  # Belarus
HERO_SMS_SERVICES = ("ot", "wa", "oi", "ds", "am", "tg", "fb", "bl")
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
CODE_PATTERNS = [
    re.compile(r"(?:code[^\d]{0,40})(\d{4,8})", re.IGNORECASE),
    re.compile(r"\b(\d{4,8})\b"),
]


class HeroSmsClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _get(self, **params: Any) -> str:
        params["api_key"] = self.api_key
        resp = requests.get(HERO_SMS_BASE, params=params, timeout=30)
        resp.raise_for_status()
        return resp.text.strip()

    def balance(self) -> str:
        return self._get(action="getBalance")

    def buy_number(self) -> tuple[str, str, str]:
        last_error = "NO_NUMBERS"
        for service in HERO_SMS_SERVICES:
            text = self._get(action="getNumber", service=service, country=HERO_SMS_COUNTRY_BY)
            if text == "NO_BALANCE":
                last_error = f"{service}: NO_BALANCE"
                continue
            if text == "NO_NUMBERS":
                last_error = f"{service}: NO_NUMBERS"
                continue
            match = re.match(r"ACCESS_NUMBER:(\d+):(\+\d+)", text)
            if match:
                print(f"HeroSMS service={service}")
                return match.group(1), match.group(2), service
            last_error = f"{service}: {text}"
        bal = self.balance()
        if bal.startswith("ACCESS_BALANCE:") and float(bal.split(":", 1)[1]) <= 0:
            raise RuntimeError("HeroSMS balance is empty. Top up at https://hero-sms.com/")
        raise RuntimeError(f"No Belarus numbers on HeroSMS ({last_error}).")

    def wait_sms(self, activation_id: str, *, timeout: float = 300, poll: float = 5) -> str:
        deadline = time.time() + timeout
        while time.time() < deadline:
            text = self._get(action="getStatus", id=activation_id)
            if text.startswith("STATUS_OK:"):
                return text.split(":", 1)[1]
            if text.startswith("STATUS_WAIT_RETRY:"):
                return text.split(":", 1)[1]
            if text in {"STATUS_CANCEL", "NO_ACTIVATION"}:
                raise RuntimeError(f"HeroSMS activation failed: {text}")
            time.sleep(poll)
        raise TimeoutError("HeroSMS SMS timeout")

    def cancel(self, activation_id: str) -> None:
        self._get(action="setStatus", status=8, id=activation_id)

    def complete(self, activation_id: str) -> None:
        self._get(action="setStatus", status=6, id=activation_id)


class AvbyClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.token: str | None = None
        self.refresh_token: str | None = None

    def _headers(self, *, auth: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-device-type": "web.desktop",
            "Origin": "https://av.by",
            "Referer": "https://av.by/",
            "X-Api-Key": self.api_key,
        }
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def login(self, email: str, password: str, *, captcha_token: str = "") -> dict[str, Any]:
        resp = requests.post(
            f"{AVBY_BASE}/auth/login/sign-in",
            impersonate="chrome124",
            timeout=30,
            headers=self._headers(),
            json={
                "login": email,
                "password": password,
                "googleRecaptcha2InvisibleToken": captcha_token,
            },
        )
        if resp.status_code != 200:
            raise RuntimeError(f"av.by login failed: {resp.status_code} {resp.text[:400]}")
        data = resp.json()
        self.token = data.get("token")
        self.refresh_token = data.get("refreshToken")
        return data

    def me(self) -> dict[str, Any]:
        resp = requests.get(
            f"{AVBY_BASE}/users/me",
            impersonate="chrome124",
            timeout=30,
            headers=self._headers(auth=True),
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _phone_payload(full_phone: str) -> dict[str, Any]:
        digits = re.sub(r"\D", "", full_phone)
        if digits.startswith("375"):
            digits = digits[3:]
        return {"phone": {"country": 1, "number": digits}}

    def request_phone_verification(self, phone: str) -> dict[str, Any]:
        resp = requests.post(
            f"{AVBY_BASE}/users/me/phone-verification-request",
            impersonate="chrome124",
            timeout=30,
            headers=self._headers(auth=True),
            json=self._phone_payload(phone),
        )
        return {"status": resp.status_code, "body": _safe_json(resp)}

    def confirm_phone_verification(self, sms_token: str, *, re_verify: bool = False) -> dict[str, Any]:
        resp = requests.post(
            f"{AVBY_BASE}/users/me/phone-verification",
            impersonate="chrome124",
            timeout=30,
            headers=self._headers(auth=True),
            json={"smsToken": sms_token, "reVerify": re_verify},
        )
        return {"status": resp.status_code, "body": _safe_json(resp)}


def _safe_json(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text


def _extract_code(raw: str) -> str:
    for pattern in CODE_PATTERNS:
        match = pattern.search(raw)
        if match:
            return match.group(1)
    cleaned = re.sub(r"\D", "", raw)
    if 4 <= len(cleaned) <= 8:
        return cleaned
    raise ValueError(f"Cannot extract SMS code from: {raw!r}")


def _account_dict_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": row.get("email"),
        "name": row.get("name"),
        "mailtm_password": row.get("mailtm_password"),
        "avby_password": row.get("avby_password"),
        "api_key": row.get("api_key"),
        "auth_token": row.get("auth_token"),
        "email_token": row.get("email_token"),
        "status": row.get("status"),
    }


def _load_account_from_db(email: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == email.lower()).first()
        if account is None:
            raise SystemExit(f"Account not found in DB: {email}")
        return {
            "email": account.email,
            "name": account.name,
            "mailtm_password": account.mailtm_password,
            "avby_password": account.avby_password,
            "api_key": account.api_key,
            "auth_token": account.auth_token,
            "email_token": account.email_token,
            "status": account.status,
            "purpose": account.purpose,
            "daily_vin_limit": account.daily_vin_limit,
        }
    finally:
        db.close()


def _load_account_from_json(email: str) -> dict[str, Any]:
    path = Path("data/avby_service_accounts.json")
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    for row in data.get("accounts") or []:
        if row.get("email", "").lower() == email.lower():
            return _account_dict_from_row(row)
    raise SystemExit(f"Account not found in JSON: {email}")


def _load_account(email: str, *, from_db: bool = False) -> dict[str, Any]:
    if from_db:
        return _load_account_from_db(email)
    try:
        return _load_account_from_json(email)
    except FileNotFoundError:
        return _load_account_from_db(email)


def _normalize_by_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("375"):
        national = digits[3:]
    else:
        national = digits
    if len(national) != 9:
        raise ValueError(f"Expected 9-digit BY national number, got: {raw!r}")
    return f"+375{national}"


def _save_verified_account(account: dict[str, Any], avby: AvbyClient, *, phone: str, verified: bool) -> None:
    note = f"phone={phone}; verified={verified}"
    if account.get("purpose") == "vin_test":
        note += "; vin_test"
    account.update(
        {
            "auth_token": avby.token,
            "status": "phone_verified" if verified else account.get("status", "confirmed"),
            "is_active": verified,
            "notes": note,
        }
    )
    db = SessionLocal()
    try:
        upsert_avby_service_account(db, account)
    finally:
        db.close()

    path = Path("data/avby_service_accounts.json")
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        for row in raw.get("accounts") or []:
            if row.get("email", "").lower() == account["email"].lower():
                row["phone"] = phone
                row["is_phone_verified"] = verified
                row["auth_token"] = avby.token
                row["status"] = account["status"]
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    vin_path = Path("data/avby_vin_test_account.json")
    if vin_path.exists():
        raw = json.loads(vin_path.read_text(encoding="utf-8"))
        if raw.get("email", "").lower() == account["email"].lower():
            raw.update(
                {
                    "phone": phone,
                    "is_phone_verified": verified,
                    "auth_token": avby.token,
                    "status": account["status"],
                }
            )
            vin_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("saved account phone verification state")


def _list_accounts() -> None:
    print("=== DB accounts ===")
    db = SessionLocal()
    try:
        rows = db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.id).all()
        if not rows:
            print("(empty)")
        for row in rows:
            extra = ""
            if row.purpose == "vin_test":
                extra = f" vin_limit={row.daily_vin_limit} used={row.vin_checks_today}"
            print(f"  #{row.id} {row.email} status={row.status} active={row.is_active}{extra}")
    finally:
        db.close()

    path = Path("data/avby_service_accounts.json")
    if path.exists():
        print("\n=== JSON accounts ===")
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("accounts") or []:
            print(f"  {row.get('email')} status={row.get('status')}")


def _login_avby(account: dict[str, Any]) -> AvbyClient:
    avby = AvbyClient(account["api_key"])
    captcha_token = ""
    captcha_api_key = _captcha_env_api_key()
    if captcha_api_key:
        print("Solving av.by login reCAPTCHA via 2captcha...")
        captcha_token = solve_recaptcha_invisible(api_key=captcha_api_key, page_url="https://av.by/")
    else:
        print("warning: CAPTCHA_2CAPTCHA_API_KEY not set; login may fail from VM IP")
    login_data = avby.login(account["email"], account["avby_password"], captcha_token=captcha_token)
    print("login ok, user id:", (login_data.get("user") or {}).get("id"))
    return avby


def _run_manual_phone_verify(account: dict[str, Any], avby: AvbyClient, *, manual_phone: str, sms_code: str | None) -> None:
    phone = _normalize_by_phone(manual_phone)
    print("manual phone:", phone)

    if sms_code:
        confirmed = avby.confirm_phone_verification(sms_code)
        print("confirm:", json.dumps(confirmed, ensure_ascii=False))
        if confirmed["status"] not in (200, 201):
            raise SystemExit("Phone confirm failed")
        me_after = avby.me()
        print("after:", json.dumps(me_after, ensure_ascii=False, indent=2)[:1000])
        verified = bool(me_after.get("isPhoneVerified"))
        _save_verified_account(account, avby, phone=phone, verified=verified)
        return

    request = avby.request_phone_verification(phone)
    print("phone verification request:", json.dumps(request, ensure_ascii=False))
    if request["status"] not in (200, 201):
        raise SystemExit(1)

    pending = (request.get("body") or {}).get("pendingPhone") if isinstance(request.get("body"), dict) else None
    if pending:
        print("pendingPhone:", json.dumps(pending, ensure_ascii=False))
    print("\nSMS sent. Re-run with --sms-code CODE when you receive it:")
    print(f"  python tools/verify_avby_phone.py --from-db --email {account['email']} --manual-phone {manual_phone} --sms-code CODE")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify av.by account phone via HeroSMS")
    parser.add_argument("--email")
    parser.add_argument("--from-db", action="store_true", help="Load credentials from avby_service_accounts table")
    parser.add_argument("--list-accounts", action="store_true", help="List av.by service accounts and exit")
    parser.add_argument("--hero-api-key", default=os.environ.get("HERO_SMS_API_KEY"))
    parser.add_argument("--hero-activation-id", help="Reuse existing HeroSMS activation id")
    parser.add_argument("--phone", help="Phone number for reuse mode (+375...)")
    parser.add_argument("--sms-timeout", type=int, default=600, help="Seconds to wait for HeroSMS SMS")
    parser.add_argument("--request-only", action="store_true", help="Only send phone verification request (no HeroSMS purchase)")
    parser.add_argument("--dry-run", action="store_true", help="Do not buy HeroSMS number")
    parser.add_argument("--manual-phone", help="Real BY phone (9 digits, e.g. 291234567) — no HeroSMS needed")
    parser.add_argument("--sms-code", help="SMS code from av.by (use with --manual-phone)")
    args = parser.parse_args()

    if args.list_accounts:
        _list_accounts()
        return

    if not args.email:
        raise SystemExit("Pass --email or use --list-accounts")

    manual_mode = bool(args.manual_phone)
    if not manual_mode and not args.hero_api_key and not args.dry_run and not args.request_only:
        raise SystemExit("Set HERO_SMS_API_KEY or use --manual-phone for real BY number")

    account = _load_account(args.email, from_db=args.from_db)
    avby = _login_avby(account)

    me_before = avby.me()
    print(
        "before:",
        json.dumps(
            {k: me_before.get(k) for k in ["email", "isPhoneVerified", "phone", "pendingPhone"]},
            ensure_ascii=False,
        ),
    )
    if me_before.get("isPhoneVerified"):
        print("Phone already verified, nothing to do.")
        return

    if manual_mode:
        _run_manual_phone_verify(account, avby, manual_phone=args.manual_phone, sms_code=args.sms_code)
        return

    hero = HeroSmsClient(args.hero_api_key)
    print("HeroSMS balance:", hero.balance())

    activation_id = phone = None
    try:
        balance = hero.balance()
        if not balance.startswith("ACCESS_BALANCE:"):
            raise RuntimeError(f"Unexpected HeroSMS balance response: {balance}")
        if (
            float(balance.split(":", 1)[1]) <= 0
            and not args.dry_run
            and not args.request_only
            and not (args.hero_activation_id and args.phone)
        ):
            raise SystemExit(
                "HeroSMS balance is 0. Top up at https://hero-sms.com/ before running verification."
            )

        if args.dry_run:
            phone = "+375290000000"
            print("dry-run phone", phone)
        elif args.request_only:
            phone = "+375290000000"
            print("request-only mode uses dummy phone for payload test:", phone)
        elif args.hero_activation_id and args.phone:
            activation_id = args.hero_activation_id
            phone = args.phone
            print("reuse HeroSMS number:", phone, "activation:", activation_id)
        else:
            activation_id, phone, _service = hero.buy_number()
            print("HeroSMS number:", phone, "activation:", activation_id)

        request = avby.request_phone_verification(phone)
        print("phone verification request:", json.dumps(request, ensure_ascii=False))

        if request["status"] not in (200, 201):
            if activation_id:
                hero.cancel(activation_id)
            raise SystemExit(1)

        pending = (request.get("body") or {}).get("pendingPhone") if isinstance(request.get("body"), dict) else None
        if pending:
            print("pendingPhone:", json.dumps(pending, ensure_ascii=False))

        if args.dry_run or args.request_only:
            return

        raw_sms = hero.wait_sms(activation_id, timeout=float(args.sms_timeout))
        print("HeroSMS raw SMS:", raw_sms)
        code = _extract_code(raw_sms)
        print("extracted code:", code)

        confirmed = avby.confirm_phone_verification(code)
        print("confirm:", json.dumps(confirmed, ensure_ascii=False))
        if confirmed["status"] not in (200, 201):
            raise SystemExit("Phone confirm failed")

        if activation_id:
            hero.complete(activation_id)

        me_after = avby.me()
        print("after:", json.dumps(me_after, ensure_ascii=False, indent=2)[:1000])

        verified = bool(me_after.get("isPhoneVerified"))
        _save_verified_account(account, avby, phone=phone, verified=verified)

    except Exception:
        if activation_id and not args.hero_activation_id:
            try:
                hero.cancel(activation_id)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
