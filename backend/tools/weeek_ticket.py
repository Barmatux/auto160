"""Update Weeek tasks: move to column, append agent note (via task recreate)."""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from typing import Any

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
COL_TEST = 8
COL_IN_PROGRESS = 5


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def get_task(token: str, task_id: int) -> dict[str, Any]:
    r = requests.get(f"{BASE}/tm/tasks/{task_id}", headers=headers(token), timeout=30)
    r.raise_for_status()
    return r.json()["task"]


def create_task(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(f"{BASE}/tm/tasks", headers=headers(token), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"POST /tm/tasks failed: {r.status_code} {r.text[:400]}")
    return r.json()["task"]


def delete_task(token: str, task_id: int) -> None:
    r = requests.delete(f"{BASE}/tm/tasks/{task_id}", headers=headers(token), timeout=30)
    if r.status_code not in (200, 204):
        raise RuntimeError(f"DELETE /tm/tasks/{task_id} failed: {r.status_code} {r.text[:400]}")


def move_task(token: str, task_id: int, board_column_id: int) -> dict[str, Any]:
    r = requests.put(
        f"{BASE}/tm/tasks/{task_id}",
        headers=headers(token),
        json={"boardColumnId": board_column_id},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["task"]


def append_note_and_move(
    token: str,
    task_id: int,
    note: str,
    *,
    board_column_id: int = COL_TEST,
    dry_run: bool = False,
) -> int:
    task = get_task(token, task_id)
    sub_tasks = task.get("subTasks") or []
    if sub_tasks:
        raise RuntimeError(f"Task #{task_id} is an epic with subtasks; update subtasks instead")

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    block = f'<p><strong>Agent {stamp}:</strong> {note}</p>'
    description = (task.get("description") or "").strip() + block

    payload: dict[str, Any] = {
        "title": task["title"],
        "projectId": task["projectId"],
        "boardId": task["boardId"],
        "boardColumnId": board_column_id,
        "description": description,
    }
    if task.get("parentId") is not None:
        payload["parentId"] = task["parentId"]
    if task.get("isCompleted"):
        payload["isCompleted"] = 1

    if dry_run:
        print(f"DRY #{task_id} -> col={board_column_id}: {task['title'][:70]}")
        print(f"  note: {note[:200]}")
        return task_id

    new_task = create_task(token, payload)
    new_id = int(new_task["id"])
    saved = (get_task(token, new_id).get("description") or "").strip()
    if block.strip() not in saved:
        delete_task(token, new_id)
        raise RuntimeError(f"New task #{new_id} missing agent note; rolled back")

    delete_task(token, task_id)
    print(f"#{task_id} -> #{new_id} [col={board_column_id}] {task['title'][:70]}")
    return new_id


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Move Weeek task and append agent comment")
    parser.add_argument("task_id", type=int)
    parser.add_argument("--note", required=True, help="Agent comment (HTML allowed)")
    parser.add_argument("--column", type=int, default=COL_TEST, help="Target boardColumnId (8=Тест)")
    parser.add_argument("--move-only", action="store_true", help="Only PUT column, no description note")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    if args.move_only:
        if args.dry_run:
            task = get_task(token, args.task_id)
            print(f"DRY move #{args.task_id} -> col {args.column}: {task['title']}")
            return
        move_task(token, args.task_id, args.column)
        print(f"Moved #{args.task_id} to column {args.column}")
        return

    append_note_and_move(
        token,
        args.task_id,
        args.note,
        board_column_id=args.column,
        dry_run=args.dry_run,
    )
    time.sleep(0.35)


if __name__ == "__main__":
    main()
