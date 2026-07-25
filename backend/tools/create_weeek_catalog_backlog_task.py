"""Create Weeek task for catalog backlog gaps (catalog_backlog.json)."""

from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"
PROJECT_ID = 1
BOARD_ID = 2
COL_TODO = 4
PARENT_EPIC_ID = 16  # R0.1 — Каталог и UI

BACKLOG_PATH = Path(__file__).resolve().parent.parent / "data" / "catalog_backlog.json"

KIND_LABELS = {
    "zero_modifications": "0 модификаций после import_avby.py",
    "needs_rating": "Нужен рейтинг от Романа",
    "needs_url": "Нужен URL на av.by",
}


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _build_description(data: dict) -> str:
    lines = [
        f"<p><strong>Источник:</strong> {html.escape(data.get('source', ''))}</p>",
        "<p><strong>Контекст:</strong> после импорта Hyundai/Subaru (25.07.2026) остались пропуски.</p>",
        "<p><strong>Порядок добавления:</strong></p>",
        "<ol>",
        "<li>avby_urls.txt</li>",
        "<li>python tools/import_avby.py --urls-file …</li>",
        "<li>data/catalog_ratings.json</li>",
        "<li>python tools/import_catalog_ratings.py</li>",
        "</ol>",
    ]

    grouped: dict[str, list[dict]] = {}
    for item in data.get("items", []):
        if item.get("status") != "pending":
            continue
        grouped.setdefault(item.get("kind", "other"), []).append(item)

    for kind, label in KIND_LABELS.items():
        items = grouped.get(kind, [])
        if not items:
            continue
        lines.append(f"<p><strong>{html.escape(label)}</strong></p><ul>")
        for item in items:
            text = html.escape(item.get("label", ""))
            url = item.get("source_url")
            if url:
                text += f' — <a href="{html.escape(url)}">{html.escape(url)}</a>'
            note = item.get("note")
            if note:
                text += f" ({html.escape(note)})"
            lines.append(f"<li>{text}</li>")
        lines.append("</ul>")

    lines.append(
        f"<p><em>Локальный трекер: backend/data/catalog_backlog.json ({len(data.get('items', []))} пунктов)</em></p>"
    )
    return "".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    data = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    pending = [i for i in data.get("items", []) if i.get("status") == "pending"]
    title = data.get("title") or "Каталог av.by — пропуски"

    payload = {
        "title": title,
        "projectId": PROJECT_ID,
        "boardId": BOARD_ID,
        "boardColumnId": COL_TODO,
        "parentId": PARENT_EPIC_ID,
        "description": _build_description(data),
    }

    r = requests.post(f"{BASE}/tm/tasks", headers=_headers(token), json=payload, timeout=30)
    if r.status_code not in (200, 201):
        raise SystemExit(f"POST /tm/tasks failed: {r.status_code} {r.text[:500]}")

    task = r.json().get("task") or {}
    task_id = task.get("id")
    print(f"Created Weeek task #{task_id}: {title}")
    print(f"Pending items: {len(pending)}")
    print(f"Parent epic: #{PARENT_EPIC_ID} (R0.1 — Каталог и UI)")


if __name__ == "__main__":
    main()
