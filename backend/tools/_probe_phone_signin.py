#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
os.chdir(ROOT_DIR)

from app.avby_session import _captcha_api_key, _solve_recaptcha
from app.db import SessionLocal
from app.models import AvbyServiceAccount
from curl_cffi import requests

AVBY_BASE = "https://web-api.av.by"
PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"
BELARUS_COUNTRY_ID = 1
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def main() -> None:
    account_id = int(sys.argv[1]) if len(sys.argv) > 1 else 29
    db = SessionLocal()
    acc = db.get(AvbyServiceAccount, account_id)
    db.close()
    if not acc or not acc.phone or not acc.avby_password:
        raise SystemExit("need phone account")

    key = _captcha_api_key()
    captcha = _solve_recaptcha(key)

    for label, url, payload in [
        (
            "generic sign-in",
            f"{AVBY_BASE}/auth/login/sign-in",
            {
                "login": acc.phone,
                "password": acc.avby_password,
                "googleRecaptcha2InvisibleToken": captcha,
            },
        ),
        (
            "phone sign-in",
            f"{AVBY_BASE}/auth/phone/sign-in",
            {
                "phone": {"country": BELARUS_COUNTRY_ID, "number": acc.phone},
                "password": acc.avby_password,
                "googleRecaptcha2InvisibleToken": captcha,
            },
        ),
    ]:
        resp = requests.post(
            url,
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
            json=payload,
        )
        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = {"raw": resp.text[:200]}
        print(
            label,
            json.dumps(
                {
                    "status": resp.status_code,
                    "message": body.get("message"),
                    "messageText": body.get("messageText"),
                    "has_token": bool(body.get("token")),
                },
                ensure_ascii=False,
            ),
        )
        if resp.status_code == 200:
            return
        captcha = _solve_recaptcha(key)


if __name__ == "__main__":
    main()
