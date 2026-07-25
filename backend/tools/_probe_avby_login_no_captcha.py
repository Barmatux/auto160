#!/usr/bin/env python3
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

db = SessionLocal()
acc = db.get(AvbyServiceAccount, 22)
if not acc:
    raise SystemExit("account 22 missing")

login = acc.email
password = acc.avby_password
print(f"testing login without captcha: {login}")

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
        "X-Api-Key": API_KEY,
    },
    json={
        "login": login,
        "password": password,
        "googleRecaptcha2InvisibleToken": "",
    },
)
print(f"status={resp.status_code}")
print(f"body={resp.text[:500]}")
db.close()
