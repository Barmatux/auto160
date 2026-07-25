#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from app.avby_accounts import avby_login_identifier, format_avby_phone_display
from app.avby_session import _captcha_api_key, _solve_recaptcha
from app.db import SessionLocal
from app.models import AvbyServiceAccount
from curl_cffi import requests

AVBY_BASE = "https://web-api.av.by"
PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def login_attempt(login: str, password: str, captcha: str) -> dict:
    resp = requests.post(
        f"{AVBY_BASE}/auth/login/sign-in",
        impersonate="chrome124",
        timeout=30,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-device-type": "web.desktop",
            "Origin": "https://av.by",
            "Referer": "https://av.by/",
            "X-Api-Key": PUBLIC_API_KEY,
        },
        json={
            "login": login,
            "password": password,
            "googleRecaptcha2InvisibleToken": captcha,
        },
    )
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw": resp.text[:300]}
    return {
        "login_repr": repr(login),
        "login_len": len(login),
        "password_len": len(password),
        "status": resp.status_code,
        "message": body.get("message"),
        "messageText": body.get("messageText"),
        "ok": resp.status_code == 200,
    }


def main() -> None:
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    db = SessionLocal()
    if account_id:
        accounts = [db.get(AvbyServiceAccount, account_id)]
    else:
        accounts = (
            db.query(AvbyServiceAccount)
            .filter(AvbyServiceAccount.phone.isnot(None))
            .order_by(AvbyServiceAccount.id.desc())
            .limit(5)
            .all()
        )
    db.close()

    key = _captcha_api_key()
    if not key:
        raise SystemExit("no captcha key")

    for acc in accounts:
        if not acc:
            continue
        print(f"\n=== account #{acc.id} ===")
        print(f"phone_db={acc.phone!r} display={format_avby_phone_display(acc.phone)!r}")
        print(f"email_db={acc.email!r}")
        print(f"login_id={avby_login_identifier(acc)!r}")
        print(f"password_len={len(acc.avby_password or '')}")
        print(f"password_has_space={(' ' in (acc.avby_password or ''))}")
        if not acc.avby_password:
            print("skip: no password")
            continue

        captcha = _solve_recaptcha(key)
        print(f"captcha_len={len(captcha)}")

        variants = []
        if acc.phone:
            national = acc.phone
            variants.extend([
                national,
                f"+375{national}",
                f"375{national}",
            ])
        if acc.email:
            variants.append(acc.email.strip())

        seen = set()
        for login in variants:
            if login in seen:
                continue
            seen.add(login)
            result = login_attempt(login, acc.avby_password, captcha)
            print(json.dumps(result, ensure_ascii=False))
            if result["ok"]:
                print("SUCCESS")
                return
            # captcha single-use; need new captcha for next variant
            captcha = _solve_recaptcha(key)
            print(f"next captcha_len={len(captcha)}")


if __name__ == "__main__":
    main()
