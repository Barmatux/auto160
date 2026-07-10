import re
import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

# find confirmPhone and nearby functions
idx = js.find("t.confirmPhone=function")
print(js[idx : idx + 800])

idx2 = js.find("phone-verification-request")
# search backwards for function definition
start = js.rfind("function", 0, idx2)
print("\n\nback context:", js[start : idx2 + 200])

# all posts containing phone:{country
for m in re.finditer(r"post\([^\)]*PHONE[^\)]*\{[^\}]{0,200}\}", js):
    s = m.group(0)
    if "VERIFICATION" in s or "verification" in s:
        print("\nPOST:", s[:300])
