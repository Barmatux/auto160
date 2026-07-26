"""Third-party marketing analytics (Yandex Metrika)."""

from __future__ import annotations

from fastapi import Request

from app.config import settings

SKIP_METRIKA_PREFIXES = (
    "/admin",
    "/api/",
    "/static/",
    "/media/",
)


def normalize_yandex_metrika_id(raw: str | None) -> str | None:
    cleaned = (raw or "").strip()
    if cleaned.isdigit():
        return cleaned
    return None


def yandex_metrika_context(request: Request) -> dict[str, str | None]:
    counter_id = normalize_yandex_metrika_id(settings.yandex_metrika_id)
    if counter_id is None:
        return {"yandex_metrika_id": None}
    path = request.url.path
    if any(path.startswith(prefix) for prefix in SKIP_METRIKA_PREFIXES):
        return {"yandex_metrika_id": None}
    return {"yandex_metrika_id": counter_id}
