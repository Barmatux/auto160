#!/usr/bin/env python3
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

SITE_KEY = "6LewiPMbAAAAAGivApIOmNe4pIjnoWgi5gjRdcW2"


def parse_2captcha_response(text: str) -> dict:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"status": 0, "request": text, "raw": text}


def main() -> None:
    key = (os.environ.get("CAPTCHA_2CAPTCHA_API_KEY") or "").strip()
    base = os.environ.get("CAPTCHA_API_URL", "https://2captcha.com").rstrip("/")
    print(f"key_set={bool(key)} base={base}")

    for attempt in range(1, 8):
        print(f"\n--- attempt {attempt} ---")
        submit = parse_2captcha_response(
            requests.post(
                f"{base}/in.php",
                data={
                    "key": key,
                    "method": "userrecaptcha",
                    "googlekey": SITE_KEY,
                    "pageurl": "https://av.by/",
                    "invisible": 1,
                    "json": 1,
                },
                timeout=30,
            ).text
        )
        print("submit", submit)
        if submit.get("status") != 1:
            time.sleep(10)
            continue

        task_id = submit["request"]
        deadline = time.time() + 240
        while time.time() < deadline:
            time.sleep(5)
            raw = requests.get(
                f"{base}/res.php",
                params={"key": key, "action": "get", "id": task_id, "json": 1},
                timeout=30,
            ).text
            poll = parse_2captcha_response(raw)
            req = str(poll.get("request") or "")
            print("poll", poll if poll.get("status") != 1 else {"status": 1, "token_len": len(req)})
            if poll.get("status") == 1 and req:
                # test av.by accepts token shape
                resp = requests.post(
                    "https://web-api.av.by/auth/login/sign-in",
                    impersonate="chrome124",
                    timeout=30,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "x-device-type": "web.desktop",
                        "Origin": "https://av.by",
                        "Referer": "https://av.by/",
                        "X-Api-Key": "x6ba5b05f090d4441cd4fac",
                    },
                    json={
                        "login": "fake@example.com",
                        "password": "wrong",
                        "googleRecaptcha2InvisibleToken": req,
                    },
                )
                body = resp.json()
                print(
                    "avby_test",
                    resp.status_code,
                    body.get("message"),
                    body.get("messageText"),
                )
                if body.get("message") == "exception.auth.invalid_sign_in":
                    print("VERDICT: integration OK (captcha accepted, credentials rejected)")
                elif body.get("message") == "exception.auth.invalid_captcha_token":
                    print("VERDICT: integration problem (av.by rejected captcha token)")
                return
            if req not in {"CAPCHA_NOT_READY", ""}:
                print("poll_terminal", poll)
                break
        time.sleep(10)

    print("VERDICT: 2captcha service did not deliver token in time")


if __name__ == "__main__":
    main()
