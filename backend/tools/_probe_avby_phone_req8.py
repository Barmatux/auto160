import sys
from curl_cffi import requests

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

js = requests.get(
    "https://static-new.av.by/app/_next/static/chunks/pages/_app-3016da327db72ddc.js",
    impersonate="chrome124",
    timeout=30,
).text

idx = js.find("profile/settings/phone")
while idx != -1:
    print(js[idx - 250 : idx + 400])
    print("\n---\n")
    idx = js.find("profile/settings/phone", idx + 1)

# search USERS_ME_PHONE_VERIFICATION_REQUEST in post calls - minified variable d.A.USERS_ME_PHONE_VERIFICATION_REQUEST
needle = "USERS_ME_PHONE_VERIFICATION_REQUEST"
pos = 0
posts = []
while True:
    pos = js.find(needle, pos)
    if pos == -1:
        break
    chunk = js[pos : pos + 800]
    if ".post(" in js[pos - 300 : pos + 800]:
        posts.append(js[pos - 300 : pos + 800])
    pos += 1
print("post usages", len(posts))
for p in posts:
    print(p[:600])
    print("---")
