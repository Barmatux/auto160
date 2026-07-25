"""Fetch epic #28 and #36 subtask details."""

from __future__ import annotations

import os
import sys

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
COLS = {4: "К работе", 5: "В работе", 6: "Готово", 7: "Отложено", 8: "Тест"}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    for epic_id in (28, 36):
        t = requests.get(f"{BASE}/tm/tasks/{epic_id}", headers=headers, timeout=30).json()["task"]
        col = COLS.get(t.get("boardColumnId"), t.get("boardColumnId"))
        print(f"=== EPIC #{epic_id}: {t['title']} [{col}] ===")
        desc = (t.get("description") or "").strip()
        if desc:
            print(desc[:300])
        for sid in t.get("subTasks") or []:
            s = requests.get(f"{BASE}/tm/tasks/{sid}", headers=headers, timeout=30).json()["task"]
            scol = COLS.get(s.get("boardColumnId"), s.get("boardColumnId"))
            done = "DONE" if s.get("isCompleted") else "open"
            print(f"  #{s['id']} [{scol}] {done} | {s['title']}")
        print()


if __name__ == "__main__":
    main()
