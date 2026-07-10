import re
import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

for m in re.finditer(r".{0,80}PHONE_VERIFICATION_REQUEST.{0,200}", js):
    print(m.group(0)[:260])
    print("---")
