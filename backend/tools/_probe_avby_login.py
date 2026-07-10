"""Probe av.by login for service accounts in DB."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path("/app")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from curl_cffi import requests

from app.db import SessionLocal
from app.models import AvbyServiceAccount

AVBY_BASE = "https://web-api.av.by"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = SessionLocal()
    try:
        rows = db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.id).all()
        for acc in rows:
            headers = {
                "User-Agent": UA,
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-device-type": "web.desktop",
                "Origin": "https://av.by",
                "Referer": "https://av.by/",
                "X-Api-Key": acc.api_key or "",
            }
            resp = requests.post(
                f"{AVBY_BASE}/auth/login/sign-in",
                impersonate="chrome124",
                timeout=30,
                headers=headers,
                json={"login": acc.email, "password": acc.avby_password},
            )
            ok = "OK" if resp.status_code == 200 else "FAIL"
            print(f"{ok} #{acc.id} {acc.email} -> {resp.status_code} {resp.text[:100]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
