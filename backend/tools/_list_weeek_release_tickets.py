"""List all board tasks with tag ids and subtasks."""

from __future__ import annotations

import os
import sys

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
BOARD_ID = 2
PROJECT_ID = 1
RELEASE_TAG_IDS = {1, 2}  # релиз tags on board
DESIGN_KW = ("дизайн", "design", "оформлен", "главной страниц")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    r = requests.get(
        f"{BASE}/tm/board-columns",
        params={"boardId": BOARD_ID},
        headers=headers,
        timeout=30,
    )
    cols = {c["id"]: c["name"] for c in r.json().get("boardColumns") or []}

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

    def tag_ids(task: dict) -> set[int]:
        raw = task.get("tags") or []
        out: set[int] = set()
        for tag in raw:
            if isinstance(tag, int):
                out.add(tag)
            elif isinstance(tag, dict) and tag.get("id") is not None:
                out.add(int(tag["id"]))
        return out

    def is_design(task: dict) -> bool:
        title = (task.get("title") or "").lower()
        return any(k in title for k in DESIGN_KW)

    def has_release_tag(task: dict) -> bool:
        if tag_ids(task) & RELEASE_TAG_IDS:
            return True
        title = (task.get("title") or "").lower()
        return title.startswith("r0.1")

    def inherited_release(task: dict) -> bool:
        if has_release_tag(task):
            return True
        parent_id = task.get("parentId")
        while parent_id:
            parent = by_id.get(parent_id)
            if parent is None:
                break
            if has_release_tag(parent):
                return True
            parent_id = parent.get("parentId")
        return False

    candidates = [
        t
        for t in all_tasks
        if inherited_release(t) and not is_design(t) and t.get("parentId") is not None
    ]

    print(f"Subtasks with release tag/epic: {len(candidates)}\n")
    for task in sorted(candidates, key=lambda t: (t.get("boardColumnId") or 0, t["id"])):
        col = cols.get(task.get("boardColumnId"), "?")
        tags = sorted(tag_ids(task))
        parent = by_id.get(task.get("parentId") or 0, {})
        print(
            f"#{task['id']:>3} [{col:>10}] done={task.get('isCompleted')} tags={tags}\n"
            f"     epic: {parent.get('title', '?')}\n"
            f"     {task['title']}\n"
        )

    print("\n--- Top-level release (no parent) ---")
    for task in sorted(all_tasks, key=lambda t: t["id"]):
        if task.get("parentId") is None and has_release_tag(task) and not is_design(task):
            col = cols.get(task.get("boardColumnId"), "?")
            print(f"#{task['id']} [{col}] {task['title']} tags={sorted(tag_ids(task))}")


if __name__ == "__main__":
    main()
