"""Print Weeek board overview."""

from __future__ import annotations

import os
import sys

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
BOARD_ID = 2
PROJECT_ID = 1


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    cols = {
        c["id"]: c["name"]
        for c in requests.get(
            f"{BASE}/tm/board-columns",
            params={"boardId": BOARD_ID},
            headers=headers,
            timeout=30,
        ).json().get("boardColumns")
        or []
    }

    all_tasks: list[dict] = []
    offset = 0
    while True:
        r = requests.get(
            f"{BASE}/tm/tasks",
            headers=headers,
            params={"projectId": PROJECT_ID, "boardId": BOARD_ID, "limit": 100, "offset": offset},
            timeout=30,
        )
        payload = r.json()
        batch = payload.get("tasks") or []
        all_tasks.extend(batch)
        if not payload.get("hasMore") or not batch:
            break
        offset += len(batch)

    by_id = {t["id"]: t for t in all_tasks}
    print(f"Board Release-0.1 (boardId={BOARD_ID}): {len(all_tasks)} tasks\n")

    for col_id in sorted(cols):
        col_name = cols[col_id]
        items = [t for t in all_tasks if t.get("boardColumnId") == col_id]
        if not items:
            continue
        print(f"## {col_name} ({len(items)})")
        for task in sorted(items, key=lambda t: (t.get("parentId") is not None, t.get("parentId") or 0, t["id"])):
            pid = task.get("parentId")
            prefix = "  - " if pid else "* "
            done = " [done]" if task.get("isCompleted") else ""
            parent = ""
            if pid and pid in by_id:
                parent = f" <- {by_id[pid]['title'][:50]}"
            print(f"{prefix}#{task['id']} {task['title']}{done}{parent}")
        print()


if __name__ == "__main__":
    main()
