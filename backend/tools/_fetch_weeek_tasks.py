"""Fetch Weeek task titles and descriptions."""

from __future__ import annotations

import os
import sys

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    ids = [int(x) for x in sys.argv[1:] if x.strip()]
    for tid in ids:
        r = requests.get(f"{BASE}/tm/tasks/{tid}", headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"#{tid} ERR {r.status_code}")
            continue
        t = r.json()["task"]
        print(f"=== #{tid} col={t.get('boardColumnId')} ===")
        print(t.get("title"))
        print(t.get("description") or "(no description)")
        print()


if __name__ == "__main__":
    main()
