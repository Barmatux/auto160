"""Create Release-0.1 backlog structure in Weeek board."""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from curl_cffi import requests

BASE = "https://api.weeek.net/public/v1"

# Release-0.1 board
PROJECT_ID = 1
BOARD_ID = 2
COL_TODO = 4  # К работе
COL_IN_PROGRESS = 5  # В работе
COL_DONE = 6  # Готово

EPICS: list[dict[str, Any]] = [
    {
        "title": "R0.1 — Инфраструктура и деплой",
        "column": COL_DONE,
        "tasks": [
            ("Docker Compose (api + postgres + minio)", COL_DONE, "done"),
            ("Деплой на VM (docker-compose.vm.yml)", COL_DONE, "done"),
            ("CI/CD GitHub Actions → deploy-vm.sh", COL_DONE, "done"),
            ("Alembic миграции и bootstrap admin", COL_DONE, "done"),
        ],
    },
    {
        "title": "R0.1 — Каталог и UI",
        "column": COL_DONE,
        "tasks": [
            ("Каталог из CSV (catalog_items, фильтры, пагинация)", COL_DONE, "done"),
            ("Кликабельные обложки в listings/catalog", COL_DONE, "done"),
            ("Фото комплектаций из объявлений av.by", COL_DONE, "done"),
            ("sync_catalog_photos → MinIO/S3", COL_DONE, "done"),
            ("Главная страница и навигация (шаблоны Jinja)", COL_DONE, "done"),
        ],
    },
    {
        "title": "R0.1 — Auth и админка",
        "column": COL_DONE,
        "tasks": [
            ("JWT auth (login/register/refresh)", COL_DONE, "done"),
            ("Роли guest/seller/admin", COL_DONE, "done"),
            ("Админка пользователей (/admin/users)", COL_DONE, "done"),
            ("CRUD объявлений (admin only)", COL_DONE, "done"),
            ("Refresh token в Redis/БД (production)", COL_TODO, "todo"),
        ],
    },
    {
        "title": "R0.1 — Парсинг av.by (объявления)",
        "column": COL_IN_PROGRESS,
        "tasks": [
            ("import_avby_listings.py — импорт ≤160 л.с.", COL_DONE, "done"),
            ("schedule_avby_listings_sync — каждые 20 мин", COL_DONE, "done"),
            ("Админка /admin/avby-sync (AvbySyncRun)", COL_DONE, "done"),
            ("import_avby.py — каталог модификаций", COL_DONE, "done"),
            ("avby_client.py — HTTP-клиент с авторизацией", COL_TODO, "todo"),
            ("Парсинг под сервисным аккаунтом (ротация)", COL_TODO, "todo"),
            ("refresh_token в AvbyServiceAccount", COL_TODO, "todo"),
        ],
    },
    {
        "title": "R0.1 — Сервисные аккаунты av.by",
        "column": COL_IN_PROGRESS,
        "tasks": [
            ("register_avby_accounts.py (Mail.tm + email)", COL_DONE, "done"),
            ("Админка /admin/avby-accounts", COL_DONE, "done"),
            ("2captcha для регистрации на VM", COL_DONE, "done"),
            ("HeroSMS: верификация телефона (+375)", COL_TODO, "blocked", "Ждём пополнения баланса HeroSMS (~$0.30/номер). Скрипт: tools/verify_avby_phone.py"),
            ("verify_avby_phone.py — автоматизация SMS", COL_TODO, "todo"),
        ],
    },
    {
        "title": "R0.1 — VIN проверка",
        "column": COL_TODO,
        "tasks": [
            ("Страница /inspection (mock-отчёт)", COL_DONE, "done"),
            ("vin_indicated при импорте объявлений", COL_DONE, "done"),
            ("VIN-метаданные: GET /offers/{id} при парсинге", COL_TODO, "todo"),
            ("Реальный отчёт av.by (платно ~18.5 BYN)", COL_TODO, "blocked", "После phone verify + баланс vinReportBalance"),
            ("Отображение VIN-отчёта на listing_detail", COL_TODO, "todo"),
        ],
    },
    {
        "title": "R0.1 — Качество и релиз",
        "column": COL_TODO,
        "tasks": [
            ("pytest — базовые тесты API", COL_TODO, "todo"),
            ("Секреты только в .env.vm (не в git)", COL_TODO, "todo"),
            ("Smoke-тест после деплоя (/health, catalog)", COL_TODO, "todo"),
            ("Документация README / runbook VM", COL_TODO, "todo"),
        ],
    },
]


def headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def create_task(token: str, *, title: str, column_id: int, description: str = "", parent_id: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "projectId": PROJECT_ID,
        "boardId": BOARD_ID,
        "boardColumnId": column_id,
    }
    if description:
        payload["description"] = description
    if parent_id is not None:
        payload["parentId"] = parent_id

    # try common payload shapes
    attempts = [
        payload,
        {**payload, "locations": [{"projectId": PROJECT_ID, "boardId": BOARD_ID, "boardColumnId": column_id}]},
    ]
    last_error = ""
    for body in attempts:
        r = requests.post(f"{BASE}/tm/tasks", headers=headers(token), json=body, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            task = data.get("task") or data
            return {"id": task.get("id"), "title": title, "response": data}
        last_error = f"{r.status_code} {r.text[:400]}"
    raise RuntimeError(f"Create task failed for {title!r}: {last_error}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    token = os.environ.get("WEEEK_API_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set WEEEK_API_TOKEN")

    created: list[dict[str, Any]] = []
    for epic in EPICS:
        epic_desc = f"Эпик Release-0.1 · доска Release-0.1 (boardId={BOARD_ID})"
        epic_task = create_task(
            token,
            title=epic["title"],
            column_id=epic["column"],
            description=epic_desc,
        )
        print(f"EPIC #{epic_task['id']}: {epic['title']}")
        created.append({"type": "epic", **epic_task})
        time.sleep(0.3)

        for item in epic["tasks"]:
            if len(item) == 3:
                title, col, _status = item
                desc = ""
            else:
                title, col, _status, desc = item
            sub = create_task(
                token,
                title=title,
                column_id=col,
                description=desc,
                parent_id=epic_task["id"],
            )
            print(f"  └─ #{sub['id']}: {title}")
            created.append({"type": "task", "epic": epic["title"], **sub})
            time.sleep(0.3)

    summary_path = os.path.join(os.path.dirname(__file__), "..", "data", "weeek_release_0_1_seed.json")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"boardId": BOARD_ID, "created": created}, f, ensure_ascii=False, indent=2)
    print(f"\nCreated {len(created)} items. Summary: {summary_path}")


if __name__ == "__main__":
    main()
