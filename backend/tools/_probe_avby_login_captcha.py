#!/usr/bin/env python3
"""Probe av.by login/sign-in requirements (captcha vs credentials)."""
import json
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from curl_cffi import requests
from app.db import SessionLocal
from app.models import AvbyServiceAccount

AVBY_BASE = "https://web-api.av.by"
API_KEY = "x6ba5b05f090d4441cd4fac"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def headers(api_key: str = API_KEY, token: str | None = None) -> dict[str, str]:
    h = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-device-type": "web.desktop",
        "Origin": "https://av.by",
        "Referer": "https://av.by/",
        "X-Api-Key": api_key,
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def decode_message(body: str) -> str:
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body[:200]
    msg = data.get("messageText") or data.get("message") or body[:200]
    return str(msg)


def login(*, login_id: str, password: str, captcha: str = "") -> tuple[int, str]:
    resp = requests.post(
        f"{AVBY_BASE}/auth/login/sign-in",
        impersonate="chrome124",
        timeout=30,
        headers=headers(),
        json={
            "login": login_id,
            "password": password,
            "googleRecaptcha2InvisibleToken": captcha,
        },
    )
    return resp.status_code, resp.text


def refresh(refresh_token: str, api_key: str = API_KEY) -> tuple[int, str]:
    resp = requests.post(
        f"{AVBY_BASE}/auth/token/refresh",
        impersonate="chrome124",
        timeout=30,
        headers=headers(api_key),
        json={"refreshToken": refresh_token},
    )
    return resp.status_code, resp.text[:300]


def signup_requirements() -> dict:
    resp = requests.get(
        f"{AVBY_BASE}/auth/sign-up/requirements",
        impersonate="chrome124",
        timeout=30,
        headers=headers(),
    )
    return {"status": resp.status_code, "body": resp.json() if resp.ok else resp.text[:300]}


def main() -> None:
    print("=== signup requirements (does av.by require captcha on this IP?) ===")
    req = signup_requirements()
    print(req)

    db = SessionLocal()
    try:
        good = db.get(AvbyServiceAccount, 22)
        bad = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.phone == "292678287").first()

        if good and good.email and good.avby_password:
            print("\n=== account #22 valid creds, NO captcha token ===")
            status, body = login(login_id=good.email, password=good.avby_password, captcha="")
            print(f"status={status} message={decode_message(body)}")

            if good.refresh_token:
                print("\n=== account #22 refresh token (no captcha) ===")
                r_status, r_body = refresh(good.refresh_token, good.api_key or API_KEY)
                print(f"status={r_status} body={r_body[:200]}")

        if bad and bad.avby_password:
            login_id = bad.phone or bad.email or ""
            print(f"\n=== phone account {login_id} wrong creds?, NO captcha ===")
            status, body = login(login_id=login_id, password=bad.avby_password, captcha="")
            print(f"status={status} message={decode_message(body)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
