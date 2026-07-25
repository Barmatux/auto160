#!/usr/bin/env python3
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
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def post(payload: dict, captcha: str) -> dict:
    payload = dict(payload)
    payload["googleRecaptcha2InvisibleToken"] = captcha
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
        json=payload,
    )
    try:
        body = resp.json()
    except json.JSONDecodeError:
        body = {"raw": resp.text[:200]}
    return {"status": resp.status_code, "message": body.get("message"), "messageText": body.get("messageText")}


def main() -> None:
    account_id = int(sys.argv[1])
    db = SessionLocal()
    acc = db.get(AvbyServiceAccount, account_id)
    db.close()
    if not acc or not acc.phone or not acc.avby_password:
        raise SystemExit("need phone account")

    key = _captcha_api_key()
    payloads = [
        {"login": acc.phone, "password": acc.avby_password},
        {"login": f"+375{acc.phone}", "password": acc.avby_password},
        {"login": {"country": 1, "number": acc.phone}, "password": acc.avby_password},
        {"phone": {"country": 1, "number": acc.phone}, "password": acc.avby_password},
        {"login": acc.phone, "password": acc.avby_password, "loginType": "phone"},
        {"login": acc.phone, "password": acc.avby_password, "type": "phone"},
    ]

    for payload in payloads:
        captcha = _solve_recaptcha(key)
        result = post(payload, captcha)
        print(json.dumps({"payload_keys": list(payload.keys()), "login": payload.get("login"), **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
