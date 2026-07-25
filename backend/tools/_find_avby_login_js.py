#!/usr/bin/env python3
import re
from curl_cffi import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
html = requests.get("https://av.by/", impersonate="chrome124", timeout=30, headers={"User-Agent": UA}).text
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
needles = [
    "auth/login",
    "sign-in",
    "googleRecaptcha2InvisibleToken",
    "invalid_sign_in",
    "login/sign",
]
for src in scripts:
    full = src if src.startswith("http") else "https://av.by" + src
    if not full.endswith(".js"):
        continue
    try:
        js = requests.get(full, impersonate="chrome124", timeout=30, headers={"User-Agent": UA}).text
    except Exception:
        continue
    if not any(n in js for n in needles):
        continue
    print("\n===", full, "len", len(js), "===")
    for needle in needles:
        if needle not in js:
            continue
        start = 0
        hits = 0
        while hits < 3:
            i = js.find(needle, start)
            if i < 0:
                break
            print("---", needle, "---")
            print(js[max(0, i - 120) : i + 220].replace("\n", " "))
            start = i + len(needle)
            hits += 1
