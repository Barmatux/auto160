#!/usr/bin/env python3
import re
import sys
from curl_cffi import requests

url = "https://static-new.av.by/app/_next/static/chunks/pages/_app-2120528f6660dccb.js"
js = requests.get(url, impersonate="chrome124", timeout=60).text
needles = ["AUTH_PHONE_SIGN_IN", "phone/sign-in", "signInByPhone", "phoneSignIn"]
for needle in needles:
    i = 0
    n = 0
    while n < 8:
        pos = js.find(needle, i)
        if pos < 0:
            break
        print(f"=== {needle} #{n} ===")
        print(js[max(0, pos - 150) : pos + 400].replace("\n", " "))
        i = pos + len(needle)
        n += 1