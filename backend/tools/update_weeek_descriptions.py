"""Add or replace descriptions on Weeek Release-0.1 tasks.

Weeek Public API accepts ``description`` only on POST /tm/tasks (create).
PUT /tm/tasks/{id} ignores description, so this script recreates each task:
POST copy with description -> verify -> DELETE original.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
DESCRIPTIONS_PATH = Path(__file__).resolve().parent.parent / "data" / "weeek_task_descriptions.json"
SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "weeek_release_0_1_seed.json"


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


def recreate_with_description(token: str, task_id: int, description: str, *, dry_run: bool = False) -> int:
    task = get_task(token, task_id)
    sub_tasks = task.get("subTasks") or []
    if sub_tasks:
        print(f"  #{task_id} skip epic (has {len(sub_tasks)} subtasks; PUT desc not supported on epics)")
        return task_id

    current = (task.get("description") or "").strip()
    if current == description.strip():
        print(f"  #{task_id} skip (already up to date)")
        return task_id

    payload: dict[str, Any] = {
        "title": task["title"],
        "projectId": task["projectId"],
        "boardId": task["boardId"],
        "boardColumnId": task["boardColumnId"],
        "description": description,
    }
    if task.get("parentId") is not None:
        payload["parentId"] = task["parentId"]

    if dry_run:
        print(f"  #{task_id} would recreate: {task['title'][:60]}")
        return task_id

    new_task = create_task(token, payload)
    new_id = int(new_task["id"])
    saved = (get_task(token, new_id).get("description") or "").strip()
    if not saved:
        delete_task(token, new_id)
        raise RuntimeError(f"New task #{new_id} has empty description; rolled back")

    delete_task(token, task_id)
    print(f"  #{task_id} -> #{new_id}: {task['title'][:70]}")
    return new_id


def load_descriptions() -> dict[int, str]:
    raw = json.loads(DESCRIPTIONS_PATH.read_text(encoding="utf-8"))
    return {int(k): v for k, v in raw.items()}


def update_seed_mapping(id_map: dict[int, int]) -> None:
    if not SEED_PATH.exists() or not id_map:
        return
    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for item in data.get("created", []):
        old_id = item.get("id")
        if old_id in id_map:
            item["id"] = id_map[old_id]
            item["previousId"] = old_id
    SEED_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    dry_run = "--dry-run" in sys.argv
    descriptions = load_descriptions()
    id_map: dict[int, int] = {}

    print(f"Updating {len(descriptions)} tasks (dry_run={dry_run})")
    for task_id in sorted(descriptions):
        try:
            new_id = recreate_with_description(token, task_id, descriptions[task_id], dry_run=dry_run)
            if new_id != task_id:
                id_map[task_id] = new_id
        except Exception as exc:
            print(f"  #{task_id} ERROR: {exc}")
        time.sleep(0.35)

    if id_map and not dry_run:
        update_seed_mapping(id_map)
        print(f"\nID mapping saved ({len(id_map)} tasks recreated). See {SEED_PATH.name}")
    print("Done.")


if __name__ == "__main__":
    main()
