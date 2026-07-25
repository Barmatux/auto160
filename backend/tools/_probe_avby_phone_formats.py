#!/usr/bin/env python3
"""Try av.by phone login formats with one captcha token each."""
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from curl_cffi import requests
from app.avby_session import _captcha_api_key, _solve_recaptcha
from app.db import SessionLocal
from app.models import AvbyServiceAccount

AVBY_BASE = "https://web-api.av.by"
PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def try_login(login: str, password: str) -> dict:
    key = _captcha_api_key()
    if not key:
        raise SystemExit("no captcha key")
    captcha = _solve_recaptcha(key)
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
        "login": login,
        "status": resp.status_code,
        "message": body.get("message"),
        "messageText": body.get("messageText"),
        "ok": resp.status_code == 200,
    }


def main() -> None:
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 27
    db = SessionLocal()
    acc = db.get(AvbyServiceAccount, account_id)
    db.close()
    if not acc or not acc.phone or not acc.avby_password:
        raise SystemExit(f"account #{account_id} missing phone/password")

    national = acc.phone
    variants = [
        f"+375{national}",
        national,
        f"375{national}",
    ]
    print(f"account=#{account_id} phone={national}")
    for login in variants:
        print("---")
        result = try_login(login, acc.avby_password)
        print(result)


if __name__ == "__main__":
    main()
