"""Probe Weeek API access (read-only)."""

from __future__ import annotations

import json
import os
import sys

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    endpoints = [
        ("GET", "/ws"),
        ("GET", "/user/me"),
        ("GET", "/ws/members"),
        ("GET", "/tm/projects"),
        ("GET", "/tm/tasks"),
        ("GET", "/tm/boards"),
        ("GET", "/tm/portfolios"),
    ]

    for method, path in endpoints:
        url = BASE + path
        try:
            r = requests.request(method, url, headers=headers, timeout=30)
            print(f"\n=== {method} {path} -> {r.status_code} ===")
            try:
                data = r.json()
                text = json.dumps(data, ensure_ascii=False, indent=2)
            except Exception:
                text = r.text
            print(text[:2500])
            if len(text) > 2500:
                print(f"... ({len(text)} chars total)")
        except Exception as exc:
            print(f"\n=== {method} {path} -> ERROR ===")
            print(exc)


if __name__ == "__main__":
    main()
