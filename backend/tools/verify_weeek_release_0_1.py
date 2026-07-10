"""Verify Release-0.1 backlog integrity on Weeek board."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "weeek_release_0_1_seed.json"
BOARD_ID = 2
PROJECT_ID = 1


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def load_expected() -> list[dict[str, Any]]:
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return data["created"]


def get_task(token: str, task_id: int) -> dict[str, Any] | None:
    r = requests.get(f"{BASE}/tm/tasks/{task_id}", headers=headers(token), timeout=30)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    task = r.json().get("task")
    if task and task.get("isDeleted"):
        return None
    return task


def fetch_board_tasks(token: str) -> list[dict[str, Any]]:
    all_tasks: list[dict[str, Any]] = []
    offset = 0
    limit = 100
    while True:
        r = requests.get(
            f"{BASE}/tm/tasks",
            headers=headers(token),
            params={"projectId": PROJECT_ID, "boardId": BOARD_ID, "limit": limit, "offset": offset},
            timeout=30,
        )
        r.raise_for_status()
        payload = r.json()
        batch = payload.get("tasks") or []
        all_tasks.extend(batch)
        if not payload.get("hasMore") or not batch:
            break
        offset += len(batch)
    return all_tasks


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    expected = load_expected()
    epic_ids = [e["id"] for e in expected if e["type"] == "epic"]
    task_ids = [e["id"] for e in expected if e["type"] == "task"]

    print(f"Expected: {len(epic_ids)} epics + {len(task_ids)} subtasks = {len(expected)} total\n")

    missing: list[int] = []
    wrong_title: list[str] = []
    wrong_board: list[str] = []
    no_description: list[int] = []
    wrong_parent: list[str] = []

    epic_by_title: dict[str, int] = {e["title"]: e["id"] for e in expected if e["type"] == "epic"}

    for item in expected:
        tid = item["id"]
        task = get_task(token, tid)
        if not task:
            missing.append(tid)
            continue
        if task["title"] != item["title"]:
            wrong_title.append(f"#{tid}: expected {item['title']!r}, got {task['title']!r}")
        if task.get("boardId") != BOARD_ID:
            wrong_board.append(f"#{tid} boardId={task.get('boardId')}")
        if item["type"] == "task" and not (task.get("description") or "").strip():
            no_description.append(tid)
        if item["type"] == "task":
            epic_id = epic_by_title.get(item["epic"])
            if epic_id and task.get("parentId") != epic_id:
                wrong_parent.append(f"#{tid} parentId={task.get('parentId')} expected {epic_id}")

    # Epic subTasks linkage
    subtask_mismatch: list[str] = []
    expected_by_epic: dict[int, list[int]] = {}
    for item in expected:
        if item["type"] != "task":
            continue
        epic_id = epic_by_title[item["epic"]]
        expected_by_epic.setdefault(epic_id, []).append(item["id"])

    for epic_id, want_subs in expected_by_epic.items():
        epic = get_task(token, epic_id)
        if not epic:
            continue
        got = sorted(epic.get("subTasks") or [])
        want = sorted(want_subs)
        if got != want:
            subtask_mismatch.append(f"Epic #{epic_id}: subTasks={got} expected={want}")

    # Old deleted subtask IDs (12-52 excluding epic ids) should 404
    epic_id_set = set(epic_ids)
    old_sub_ids = [i for i in range(12, 53) if i not in epic_id_set]
    stale_alive = [i for i in old_sub_ids if get_task(token, i) is not None]

    board_tasks = fetch_board_tasks(token)
    board_ids = {t["id"] for t in board_tasks}
    expected_ids = set(epic_ids + task_ids)
    extra_on_board = sorted(board_ids - expected_ids - {10})  # #10 test card
    not_on_board_list = sorted(expected_ids - board_ids)

    print("=== Per-task check ===")
    print(f"Missing/deleted: {missing or 'none'}")
    print(f"Wrong title: {len(wrong_title)}")
    for line in wrong_title[:5]:
        print(f"  - {line}")
    print(f"Wrong board: {wrong_board or 'none'}")
    print(f"Subtasks without description: {no_description or 'none'}")
    print(f"Wrong parentId: {wrong_parent or 'none'}")
    print(f"Epic subTasks mismatch: {subtask_mismatch or 'none'}")
    print(f"Old IDs still alive (12-52): {stale_alive or 'none'}")

    print("\n=== Board listing ===")
    print(f"Tasks on board (API list): {len(board_tasks)}")
    print(f"Expected IDs not in list: {not_on_board_list or 'none'}")
    print(f"Extra tasks on board: {extra_on_board or 'none'}")

    ok = (
        not missing
        and not wrong_title
        and not wrong_board
        and not no_description
        and not wrong_parent
        and not subtask_mismatch
        and not stale_alive
        and not not_on_board_list
    )
    print("\n" + ("OK: all tasks in place." if ok else "ISSUES FOUND — see above."))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
