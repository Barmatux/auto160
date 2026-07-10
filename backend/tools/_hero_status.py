import os
import sys

from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
key = os.environ["HERO_SMS_API_KEY"]
base = "https://hero-sms.com/stubs/handler_api.php"
for aid in ["573447294", "573447684", "573447723"]:
    r = requests.get(base, params={"api_key": key, "action": "getStatus", "id": aid}, timeout=30)
    print(aid, "->", r.text.strip())
