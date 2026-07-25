#!/usr/bin/env python3
import re
import sys
from curl_cffi import requests

url = sys.argv[1] if len(sys.argv) > 1 else "https://av.by/"
html = requests.get(url, impersonate="chrome124", timeout=30, headers={"User-Agent": "Mozilla/5.0"}).text
print("len", len(html))
for pat in [
    r"6L[a-zA-Z0-9_-]{38}",
    r"sign-in",
    r"googleRecaptcha",
    r"login/sign-in",
    r'"login"',
]:
    found = sorted(set(re.findall(pat, html)))
    print(pat, found[:10])

scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
print("scripts", len(scripts))
for src in scripts[:15]:
    if "av.by" in src or src.startswith("/"):
        full = src if src.startswith("http") else "https://av.by" + src
        try:
            js = requests.get(full, impersonate="chrome124", timeout=30).text
        except Exception as exc:
            print("fail", full, exc)
            continue
        if "sign-in" in js or "googleRecaptcha2InvisibleToken" in js:
            print("hit", full, "len", len(js))
            for m in re.finditer(r".{0,40}googleRecaptcha2InvisibleToken.{0,80}", js):
                print(m.group(0)[:160])
