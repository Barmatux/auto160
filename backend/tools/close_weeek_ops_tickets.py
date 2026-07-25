"""Close completed backend ops tickets on Weeek board."""

from __future__ import annotations

import os
import sys
import time

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
COL_DONE = 6

NOTES = {
    116: (
        "<p><strong>Готово (R0.1):</strong> сервис <code>avby-archive</code>, "
        "ночной прогон <code>archive_removed_avby_listings.py</code>.</p>"
        "<p>Последний run: checked=9965, archived=7, active=9957.</p>"
        "<p>Отчёт: <code>python tools/report_listing_freshness.py</code></p>"
    ),
    115: (
        "<p><strong>Готово (R0.1):</strong> <code>audit_listing_photos.py</code> + "
        "<code>backfill_listing_photos.py</code> (публичные страницы av.by).</p>"
        "<p>Backfill: 18/47 обновлено; 29 без фото (вероятно сняты с av.by — поймает archive).</p>"
        "<p>Осталось 5 seed-записей без avby_id.</p>"
    ),
    107: (
        "<p><strong>Готово:</strong> <code>scripts/smoke-vm.sh</code> — /health, /catalog, /listings.</p>"
    ),
}


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def close_with_note(token: str, task_id: int, note: str) -> None:
    task = requests.get(f"{BASE}/tm/tasks/{task_id}", headers=headers(token), timeout=30).json()["task"]
    description = (task.get("description") or "").strip()
    if note.strip() not in description:
        description = description + note
    r = requests.put(
        f"{BASE}/tm/tasks/{task_id}",
        headers=headers(token),
        json={"boardColumnId": COL_DONE, "isCompleted": 1, "description": description},
        timeout=30,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"PUT #{task_id} failed: {r.status_code} {r.text[:300]}")
    print(f"closed #{task_id}: {task['title'][:60]}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")
    for task_id, note in NOTES.items():
        close_with_note(token, task_id, note)
        time.sleep(0.35)


if __name__ == "__main__":
    main()
