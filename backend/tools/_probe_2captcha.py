#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
os.chdir(ROOT_DIR)

from curl_cffi import requests

key = (os.environ.get("CAPTCHA_2CAPTCHA_API_KEY") or os.environ.get("TWOCAPTCHA_API_KEY") or "").strip()
base = os.environ.get("CAPTCHA_API_URL", "https://2captcha.com").rstrip("/")
print(f"api_base={base}")
print(f"key_set={bool(key)}")
if not key:
    raise SystemExit("no captcha api key")

balance = requests.get(
    f"{base}/res.php",
    params={"key": key, "action": "getbalance", "json": 1},
    timeout=30,
).json()
print(f"balance={balance}")

submit = requests.post(
    f"{base}/in.php",
    data={
        "key": key,
        "method": "userrecaptcha",
        "googlekey": "6LewiPMbAAAAAGivApIOmNe4pIjnoWgi5gjRdcW2",
        "pageurl": "https://av.by/",
        "invisible": 1,
        "json": 1,
    },
    timeout=30,
).json()
print(f"submit={submit}")
if submit.get("status") != 1:
    raise SystemExit(1)

task_id = submit["request"]
deadline = time.time() + 180
poll_num = 0
while time.time() < deadline:
    time.sleep(5)
    poll_num += 1
    poll = requests.get(
        f"{base}/res.php",
        params={"key": key, "action": "get", "id": task_id, "json": 1},
        timeout=30,
    ).json()
    print(f"poll_{poll_num}={poll}")
    if poll.get("status") == 1:
        token = str(poll.get("request") or "")
        print(f"solved_len={len(token)}")
        raise SystemExit(0)
    if poll.get("request") != "CAPCHA_NOT_READY":
        raise SystemExit(2)

print("timeout_after_180s")
