import os
from curl_cffi import requests

key = os.environ["HERO_SMS_API_KEY"]
base = "https://hero-sms.com/stubs/handler_api.php"
for aid in ["573436189", "573436291", "573436334", "573447294", "573447684", "573447723"]:
    r = requests.get(base, params={"api_key": key, "action": "setStatus", "status": 8, "id": aid}, timeout=30)
    print(aid, r.text.strip())
