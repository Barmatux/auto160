"""Analyze HeroSMS + av.by phone verification feasibility.

Usage:
  set HERO_SMS_API_KEY=...
  python tools/analyze_hero_sms_avby.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from curl_cffi import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

AVBY_BASE = "https://web-api.av.by"
HERO_BASE = "https://hero-sms.com/stubs/handler_api.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def hero(api_key: str, **params) -> str:
    params["api_key"] = api_key
    r = requests.get(HERO_BASE, params=params, timeout=30)
    return r.text.strip()


def avby_headers(api_key: str, token: str | None = None) -> dict[str, str]:
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


def main() -> None:
    api_key = os.environ.get("HERO_SMS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set HERO_SMS_API_KEY")

    print("=== HeroSMS ===")
    print("balance:", hero(api_key, action="getBalance"))

    status_raw = hero(api_key, action="getNumbersStatus", country=51)
    print("BY numbers status length:", len(status_raw))
    try:
        status = json.loads(status_raw)
        ot_entries = {k: v for k, v in status.items() if k.startswith("ot_") or k == "ot"}
        print("ot service variants:", len(ot_entries))
        for k, v in list(ot_entries.items())[:8]:
            print(f"  {k}: {v}")
    except json.JSONDecodeError:
        print("status preview:", status_raw[:400])

    prices = hero(api_key, action="getPrices", country=51, service="ot")
    print("prices (ot/BY):", prices[:500])

    print("\n=== av.by account ===")
    acc = json.loads((ROOT / "data/avby_service_accounts.json").read_text(encoding="utf-8"))["accounts"][0]
    login = requests.post(
        f"{AVBY_BASE}/auth/login/sign-in",
        impersonate="chrome124",
        timeout=30,
        headers=avby_headers(acc["api_key"]),
        json={"login": acc["email"], "password": acc["avby_password"]},
    )
    print("login:", login.status_code)
    token = login.json().get("token")
    me = requests.get(
        f"{AVBY_BASE}/users/me",
        impersonate="chrome124",
        timeout=30,
        headers=avby_headers(acc["api_key"], token),
    ).json()
    print("user:", json.dumps({k: me.get(k) for k in ["id", "email", "isPhoneVerified"]}, ensure_ascii=False))

    print("\n=== av.by phone-verification-request (dummy number) ===")
    dummy_payload = {"phone": {"country": 1, "number": "291234567"}}
    req = requests.post(
        f"{AVBY_BASE}/users/me/phone-verification-request",
        impersonate="chrome124",
        timeout=30,
        headers=avby_headers(acc["api_key"], token),
        json=dummy_payload,
    )
    print("status:", req.status_code)
    print("body:", req.text[:600])

    print("\n=== av.by auth/phone/sign-up fields (new account via phone) ===")
    signup = requests.post(
        f"{AVBY_BASE}/auth/phone/sign-up",
        impersonate="chrome124",
        timeout=30,
        headers=avby_headers(acc["api_key"]),
        json={
            "name": "Test",
            "password": "TestPass123",
            "phone": {"country": 1, "number": "291234567"},
        },
    )
    print("phone sign-up:", signup.status_code, signup.text[:400])

    print("\n=== Try buy BY number (will fail if balance 0) ===")
    buy = hero(api_key, action="getNumber", service="ot", country=51)
    print("getNumber:", buy)


if __name__ == "__main__":
    main()
