import os
import sys
from pathlib import Path

ROOT = Path("/app")
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from curl_cffi import requests
from app.db import SessionLocal
from app.models import AvbyServiceAccount
from tools.register_avby_accounts import _captcha_env_api_key, solve_recaptcha_invisible

AVBY_BASE = "https://web-api.av.by"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    db = SessionLocal()
    acc = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == "avby01_w5zd63ii@web-library.net").first()
    db.close()
    captcha = solve_recaptcha_invisible(api_key=_captcha_env_api_key(), page_url="https://av.by/")
    h = {
        "User-Agent": UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-device-type": "web.desktop",
        "Origin": "https://av.by",
        "Referer": "https://av.by/",
        "X-Api-Key": acc.api_key,
    }
    login = requests.post(
        f"{AVBY_BASE}/auth/login/sign-in",
        impersonate="chrome124",
        timeout=30,
        headers=h,
        json={"login": acc.email, "password": acc.avby_password, "googleRecaptcha2InvisibleToken": captcha},
    )
    print("login", login.status_code)
    token = login.json()["token"]
    h["Authorization"] = f"Bearer {token}"
    me = requests.get(f"{AVBY_BASE}/users/me", impersonate="chrome124", timeout=30, headers=h).json()
    print("me", {k: me.get(k) for k in ["isPhoneVerified", "phone", "pendingPhone"]})


if __name__ == "__main__":
    main()
