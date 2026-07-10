import os
import sys

from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
key = os.environ.get("HERO_SMS_API_KEY", "")
base = "https://hero-sms.com/stubs/handler_api.php"
for svc in ["ot", "tg", "fb", "am", "wa", "oi", "ds", "bl"]:
    r = requests.get(
        base,
        params={"api_key": key, "action": "getNumber", "service": svc, "country": 51},
        timeout=30,
    )
    print(svc, "->", r.text.strip())
