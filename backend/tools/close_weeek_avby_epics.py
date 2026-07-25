"""Close Weeek epics #28 and #36 with notes."""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
COL_DONE = 6
COL_DEFERRED = 7

HEROSMS_NOTE = (
    "<p><strong>Закрыто (R0.1):</strong> HeroSMS для РБ не работает / не используем.</p>"
    "<p>Пока добавляем и поддерживаем av.by аккаунты <strong>вручную</strong> "
    "через админку (<code>/admin/avby-accounts</code>): email/phone + пароль, "
    "при необходимости JWT из браузера.</p>"
)

DEFERRED_ROTATION_NOTE = (
    "<p><strong>Закрыто (R0.1):</strong> не требуется для импорта объявлений — "
    "sync ходит в публичный API av.by без авторизации.</p>"
)

REFRESH_TOKEN_NOTE = (
    "<p><strong>Готово:</strong> <code>refresh_token</code> в "
    "<code>AvbyServiceAccount</code>, обновление через "
    "<code>app/avby_session.py</code> и сервис "
    "<code>keep_avby_session_alive.py</code> (VIN).</p>"
)

AVBY_CLIENT_NOTE = (
    "<p><strong>Закрыто:</strong> отдельный <code>avby_client.py</code> не нужен — "
    "HTTP/авторизация реализованы в <code>app/avby_session.py</code>.</p>"
)

EPIC_CLOSE_NOTE = (
    "<p><strong>Эпик закрыт для Release-0.1.</strong> Основной функционал на VM работает.</p>"
)


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


def put_task(token: str, task_id: int, body: dict[str, Any]) -> dict[str, Any]:
    r = requests.put(f"{BASE}/tm/tasks/{task_id}", headers=headers(token), json=body, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PUT /tm/tasks/{task_id} failed: {r.status_code} {r.text[:400]}")
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


def close_task(token: str, task_id: int) -> None:
    put_task(token, task_id, {"boardColumnId": COL_DONE, "isCompleted": 1})
    print(f"  closed #{task_id}")


def recreate_with_note(token: str, task_id: int, note_html: str, *, close: bool = True) -> int:
    task = get_task(token, task_id)
    if task.get("subTasks"):
        raise RuntimeError(f"#{task_id} is epic")

    description = (task.get("description") or "").strip()
    if note_html.strip() not in description:
        description = description + note_html

    payload: dict[str, Any] = {
        "title": task["title"],
        "projectId": task["projectId"],
        "boardId": task["boardId"],
        "boardColumnId": COL_DONE if close else task.get("boardColumnId"),
        "description": description,
    }
    if task.get("parentId") is not None:
        payload["parentId"] = task["parentId"]
    if close:
        payload["isCompleted"] = 1

    new_task = create_task(token, payload)
    new_id = int(new_task["id"])
    delete_task(token, task_id)
    print(f"  #{task_id} -> #{new_id} (note added, closed={close})")
    return new_id


def close_epic(token: str, epic_id: int) -> None:
    task = get_task(token, epic_id)
    description = (task.get("description") or "").strip()
    if EPIC_CLOSE_NOTE.strip() not in description:
        description = description + EPIC_CLOSE_NOTE
    put_task(
        token,
        epic_id,
        {
            "boardColumnId": COL_DONE,
            "isCompleted": 1,
            "description": description,
        },
    )
    print(f"closed epic #{epic_id}: {task['title']}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    print("=== Epic #28 — Парсинг av.by ===")
    for task_id in (70, 71, 72, 73):
        close_task(token, task_id)
        time.sleep(0.35)
    recreate_with_note(token, 75, DEFERRED_ROTATION_NOTE)
    time.sleep(0.35)
    recreate_with_note(token, 105, REFRESH_TOKEN_NOTE)
    time.sleep(0.35)
    recreate_with_note(token, 106, AVBY_CLIENT_NOTE)
    time.sleep(0.35)
    close_epic(token, 28)

    print("\n=== Epic #36 — Сервисные аккаунты av.by ===")
    for task_id in (77, 78, 79):
        close_task(token, task_id)
        time.sleep(0.35)
    recreate_with_note(token, 80, HEROSMS_NOTE)
    time.sleep(0.35)
    recreate_with_note(token, 81, HEROSMS_NOTE)
    time.sleep(0.35)
    close_epic(token, 36)

    print("\nDone.")


if __name__ == "__main__":
    main()
