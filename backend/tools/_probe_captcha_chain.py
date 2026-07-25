#!/usr/bin/env python3
"""Full captcha chain: 2captcha solve -> av.by login accept token."""
import json
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from curl_cffi import requests
from app.db import SessionLocal
from app.models import AvbyServiceAccount

SITE_KEY = "6LewiPMbAAAAAGivApIOmNe4pIjnoWgi5gjRdcW2"
AVBY_BASE = "https://web-api.av.by"
PUBLIC_API_KEY = "x6ba5b05f090d4441cd4fac"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def solve(api_key: str, *, pageurl: str, timeout: int = 300) -> tuple[str, dict]:
    base = os.environ.get("CAPTCHA_API_URL", "https://2captcha.com").rstrip("/")
    submit = requests.post(
        f"{base}/in.php",
        data={
            "key": api_key,
            "method": "userrecaptcha",
            "googlekey": SITE_KEY,
            "pageurl": pageurl,
            "invisible": 1,
            "json": 1,
        },
        timeout=30,
    ).json()
    if submit.get("status") != 1:
        return "", {"stage": "submit", "response": submit}

    task_id = submit["request"]
    deadline = time.time() + timeout
    polls = []
    while time.time() < deadline:
        time.sleep(5)
        poll = requests.get(
            f"{base}/res.php",
            params={"key": api_key, "action": "get", "id": task_id, "json": 1},
            timeout=30,
        ).json()
        polls.append(poll)
        if poll.get("status") == 1:
            return str(poll.get("request") or ""), {"stage": "solved", "task_id": task_id, "polls": len(polls)}
        if poll.get("request") not in {"CAPCHA_NOT_READY", None}:
            return "", {"stage": "poll_error", "task_id": task_id, "last": poll, "polls": len(polls)}
    return "", {"stage": "timeout", "task_id": task_id, "polls": len(polls), "last": polls[-1] if polls else None}


def try_login(login: str, password: str, captcha: str) -> dict:
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
    body = resp.text[:400]
    try:
        parsed = resp.json()
        msg = parsed.get("messageText") or parsed.get("message")
    except json.JSONDecodeError:
        msg = body
    return {"status": resp.status_code, "message": msg, "body": body}


def main() -> None:
    key = (os.environ.get("CAPTCHA_2CAPTCHA_API_KEY") or "").strip()
    if not key:
        raise SystemExit("no captcha key")

    db = SessionLocal()
    acc = db.get(AvbyServiceAccount, 22)
    login = acc.email if acc else "test@example.com"
    password = acc.avby_password if acc else "wrong"
    db.close()

    for pageurl in ("https://av.by/", "https://av.by/registration"):
        print(f"\n=== solve pageurl={pageurl} timeout=300s ===")
        token, meta = solve(key, pageurl=pageurl, timeout=300)
        print("meta=", meta)
        if not token:
            continue
        print(f"token_len={len(token)}")
        result = try_login(login, password, token)
        print("avby_login=", result)

    print("\n=== control: empty captcha ===")
    print(try_login(login, password, ""))


if __name__ == "__main__":
    main()
