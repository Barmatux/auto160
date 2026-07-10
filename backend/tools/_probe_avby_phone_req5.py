import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

idx = js.find("USERS_ME_PHONE_VERIFICATION_REQUEST")
while idx != -1:
    snippet = js[idx : idx + 500]
    if "post" in snippet.lower() or "phone" in snippet.lower():
        print(js[idx - 200 : idx + 500])
        print("\n---\n")
    idx = js.find("USERS_ME_PHONE_VERIFICATION_REQUEST", idx + 1)

# search function names near phone verification for logged in user
for needle in ["requestPhone", "sendPhoneVerification", "verifyPhoneRequest", "phoneVerificationRequest"]:
    idx = js.find(needle)
    if idx != -1:
        print(needle, js[idx : idx + 400])
