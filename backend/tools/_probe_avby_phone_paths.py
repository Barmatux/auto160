import re
import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

# all API paths with phone
paths = sorted(set(re.findall(r'"/([a-zA-Z0-9_\-/:{}]+phone[a-zA-Z0-9_\-/:{}]*)"', js, re.I)))
for p in paths:
    print(p)

print("\n--- phone bind / verify snippets ---")
for needle in [
    "verifyPhone",
    "confirmPhone",
    "bindPhone",
    "addPhone",
    "phoneVerification",
    "isPhoneVerified",
    "needReVerifyPhone",
    "phone/sign-up",
    "phoneToken",
    "PhoneManager",
]:
    idx = 0
    count = 0
    while count < 2:
        idx = js.find(needle, idx)
        if idx == -1:
            break
        print(f"\n[{needle}]")
        print(js[idx - 120 : idx + 280])
        idx += len(needle)
        count += 1
