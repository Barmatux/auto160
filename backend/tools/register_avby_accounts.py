"""Register av.by service accounts via disposable Mail.tm inboxes.

Example:
  python tools/register_avby_accounts.py --count 1
  python tools/register_avby_accounts.py --count 20 --delay-seconds 5 --output data/avby_service_accounts.json
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import secrets
import string
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from curl_cffi import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import upsert_avby_service_account
from app.db import SessionLocal

MAILTM_BASE = "https://api.mail.tm"
AVBY_BASE = "https://web-api.av.by"

CODE_PATTERNS = [
    re.compile(r"(?:код[^\d]{0,40})(\d{4,8})", re.IGNORECASE),
    re.compile(r"(?:code[^\d]{0,40})(\d{4,8})", re.IGNORECASE),
    re.compile(r"\b(\d{4,8})\b"),
    re.compile(r"emailToken=([A-Za-z0-9._-]+)", re.IGNORECASE),
    re.compile(r"[?&]token=([A-Za-z0-9._-]+)", re.IGNORECASE),
]


@dataclass
class RegisteredAccount:
    email: str
    mailtm_password: str
    avby_password: str
    name: str
    email_token: str
    auth_token: str | None
    api_key: str | None
    status: str
    error: str | None = None
    created_at: str = ""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _rand_local(prefix: str, length: int = 8) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(length))


def _gen_avby_password() -> str:
    # av.by requires letters + digits, min 8 chars.
    return "Avby" + secrets.token_urlsafe(10) + "1"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return {}


def _extract_verification_token(subject: str, text: str, html: str | list[str]) -> str | None:
    if isinstance(html, list):
        html_blob = "\n".join(html)
    else:
        html_blob = html or ""
    blob = "\n".join([subject or "", text or "", html_blob])
    for pattern in CODE_PATTERNS:
        match = pattern.search(blob)
        if match:
            return match.group(1)
    return None


class MailTmClient:
    def __init__(self, user_agent: str) -> None:
        self.session = requests.Session(impersonate="chrome124", timeout=30)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        }

    def create_mailbox(self, local_prefix: str) -> tuple[str, str, str]:
        domains_resp = self.session.get(f"{MAILTM_BASE}/domains", headers=self.headers)
        domains_resp.raise_for_status()
        domains = domains_resp.json()
        if isinstance(domains, dict):
            members = domains.get("hydra:member") or []
        else:
            members = domains
        if not members:
            raise RuntimeError("Mail.tm returned no domains")
        domain = members[0]["domain"]
        address = f"{_rand_local(local_prefix)}@{domain}"
        password = secrets.token_urlsafe(18)
        create_resp = self.session.post(
            f"{MAILTM_BASE}/accounts",
            headers=self.headers,
            json={"address": address, "password": password},
        )
        create_resp.raise_for_status()
        token_resp = self.session.post(
            f"{MAILTM_BASE}/token",
            headers=self.headers,
            json={"address": address, "password": password},
        )
        token_resp.raise_for_status()
        token = token_resp.json()["token"]
        return address, password, token

    def wait_for_verification_token(self, token: str, timeout_seconds: int) -> tuple[str, str]:
        headers = {**self.headers, "Authorization": f"Bearer {token}"}
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            resp = self.session.get(f"{MAILTM_BASE}/messages", headers=headers)
            resp.raise_for_status()
            raw = resp.json()
            members = raw if isinstance(raw, list) else raw.get("hydra:member") or []
            for message in members:
                msg_id = message["id"]
                full = self.session.get(f"{MAILTM_BASE}/messages/{msg_id}", headers=headers)
                full.raise_for_status()
                payload = full.json()
                code = _extract_verification_token(
                    payload.get("subject") or "",
                    payload.get("text") or payload.get("intro") or "",
                    payload.get("html") or "",
                )
                if code:
                    return code, payload.get("subject") or ""
            time.sleep(3)
        raise TimeoutError(f"Verification email not received within {timeout_seconds}s")


class AvbyAuthClient:
    def __init__(self, user_agent: str) -> None:
        self.session = requests.Session(impersonate="chrome124", timeout=30)
        self.headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://av.by",
            "Referer": "https://av.by/registration",
        }

    def sign_up_by_email(
        self,
        *,
        email: str,
        name: str,
        password: str,
        captcha_token: str | None,
    ) -> None:
        payload: dict[str, Any] = {
            "email": email,
            "name": name,
            "password": password,
            "googleRecaptcha2InvisibleToken": captcha_token or "",
        }
        resp = self.session.post(f"{AVBY_BASE}/auth/email/sign-up", headers=self.headers, json=payload)
        if resp.status_code not in {200, 201, 204}:
            raise RuntimeError(f"av.by sign-up failed: {resp.status_code} {resp.text[:500]}")

    def confirm_sign_up(self, email_token: str) -> dict[str, Any]:
        resp = self.session.post(
            f"{AVBY_BASE}/auth/email/confirm-sign-up",
            headers=self.headers,
            json={"emailToken": email_token},
        )
        if resp.status_code not in {200, 201}:
            raise RuntimeError(f"av.by confirm failed: {resp.status_code} {resp.text[:500]}")
        if not resp.text.strip():
            return {}
        return resp.json()


def _load_existing_accounts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("accounts") or []


def _save_accounts(path: Path, accounts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now(),
        "accounts": accounts,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _persist_account_to_db(account_dict: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        upsert_avby_service_account(db, account_dict)
    finally:
        db.close()


def register_one_account(
    *,
    index: int,
    local_prefix: str,
    display_name: str,
    user_agent: str,
    captcha_token: str | None,
    mail_wait_seconds: int,
) -> RegisteredAccount:
    mail_client = MailTmClient(user_agent=user_agent)
    avby_client = AvbyAuthClient(user_agent=user_agent)
    prefix = f"{local_prefix}{index:02d}_"
    email, mailtm_password, mail_token = mail_client.create_mailbox(prefix)
    avby_password = _gen_avby_password()
    print(f"[{index}] mailbox: {email}")

    avby_client.sign_up_by_email(
        email=email,
        name=display_name,
        password=avby_password,
        captcha_token=captcha_token,
    )
    print(f"[{index}] sign-up submitted, waiting for email...")

    email_token, subject = mail_client.wait_for_verification_token(mail_token, mail_wait_seconds)
    print(f"[{index}] verification code received ({subject!r})")

    confirm_payload = avby_client.confirm_sign_up(email_token)
    auth_token = confirm_payload.get("token")
    api_key = None
    if auth_token:
        api_key = _decode_jwt_payload(auth_token).get("api_key")

    print(f"[{index}] account confirmed, api_key={'yes' if api_key else 'no'}")
    return RegisteredAccount(
        email=email,
        mailtm_password=mailtm_password,
        avby_password=avby_password,
        name=display_name,
        email_token=email_token,
        auth_token=auth_token,
        api_key=api_key,
        status="confirmed",
        created_at=_utc_now(),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register av.by accounts using Mail.tm disposable inboxes")
    parser.add_argument("--count", type=int, default=1, help="How many accounts to create (start with 1, then scale)")
    parser.add_argument(
        "--output",
        default="data/avby_service_accounts.json",
        help="JSON file to append created accounts",
    )
    parser.add_argument("--prefix", default="avby", help="Local-part prefix for Mail.tm addresses")
    parser.add_argument("--name", default="Сервис Авто", help="Display name on av.by (Cyrillic)")
    parser.add_argument("--delay-seconds", type=float, default=3.0, help="Pause between accounts")
    parser.add_argument("--mail-wait-seconds", type=int, default=180, help="How long to wait for verification email")
    parser.add_argument("--captcha-token", default=None, help="googleRecaptcha2InvisibleToken if av.by starts requiring it")
    parser.add_argument("--user-agent", default="Mozilla/5.0", help="Browser User-Agent")
    parser.add_argument("--dry-run", action="store_true", help="Only create Mail.tm mailbox, skip av.by registration")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.count < 1:
        raise SystemExit("--count must be >= 1")

    output_path = Path(args.output)
    stored = _load_existing_accounts(output_path)
    created: list[dict[str, Any]] = []

    for index in range(1, args.count + 1):
        try:
            if args.dry_run:
                mail_client = MailTmClient(user_agent=args.user_agent)
                email, mailtm_password, _token = mail_client.create_mailbox(f"{args.prefix}{index:02d}_")
                account = RegisteredAccount(
                    email=email,
                    mailtm_password=mailtm_password,
                    avby_password="",
                    name=args.name,
                    email_token="",
                    auth_token=None,
                    api_key=None,
                    status="mailtm_only",
                    created_at=_utc_now(),
                )
                print(f"[{index}] dry-run mailbox: {email}")
            else:
                account = register_one_account(
                    index=index,
                    local_prefix=args.prefix,
                    display_name=args.name,
                    user_agent=args.user_agent,
                    captcha_token=args.captcha_token,
                    mail_wait_seconds=args.mail_wait_seconds,
                )
            stored.append(asdict(account))
            created.append(asdict(account))
            _save_accounts(output_path, stored)
            _persist_account_to_db(asdict(account))
        except Exception as exc:
            print(f"[{index}] failed: {exc}")
            failed = RegisteredAccount(
                email="",
                mailtm_password="",
                avby_password="",
                name=args.name,
                email_token="",
                auth_token=None,
                api_key=None,
                status="failed",
                error=str(exc),
                created_at=_utc_now(),
            )
            stored.append(asdict(failed))
            _save_accounts(output_path, stored)
            return 1

        if index < args.count and args.delay_seconds > 0:
            time.sleep(args.delay_seconds)

    print(f"Done. Created {len(created)} account(s). Saved to {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
