import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

for needle in [
    "t.requestPhoneVerification",
    "requestPhoneVerification",
    "PHONE_VERIFICATION_REQUEST",
    "phoneVerificationRequest",
    "sendPhoneVerificationRequest",
]:
    idx = 0
    while True:
        idx = js.find(needle, idx)
        if idx == -1:
            break
        print(f"\n=== {needle} @ {idx} ===")
        print(js[idx - 200 : idx + 500])
        idx += len(needle)
