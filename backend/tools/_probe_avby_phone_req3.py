import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

needle = "phone-verification-request"
idx = 0
while True:
    idx = js.find(needle, idx)
    if idx == -1:
        break
    print(js[idx - 300 : idx + 400])
    print("\n=====\n")
    idx += 1

# search verifyPhone or sendSmsToken patterns
for fn in ["verifyUserPhone", "sendSms", "smsToken", "phoneNumber", "requestVerification"]:
    pos = js.find(fn)
    if pos != -1 and "phone" in js[pos - 50 : pos + 100].lower():
        print(fn, js[pos - 80 : pos + 200])
