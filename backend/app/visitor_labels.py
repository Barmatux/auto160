"""Classify site visitors for internal analytics."""

from __future__ import annotations

import re

from fastapi import Request

INTERNAL_UA_PREFIX = "Auto160Internal/"
INTERNAL_CLIENT_HEADER = "x-auto160-client"

BOT_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("bot:yandex", "Яндекс-бот", ("yandexbot", "yandex.com/bots", "yandexrenderresources")),
    ("bot:google", "Google-бот", ("googlebot", "adsbot-google", "mediapartners-google", "google-inspectiontool")),
    ("bot:bing", "Bing-бот", ("bingbot", "msnbot")),
    ("bot:mail", "Почтовый бот", ("mail.ru_bot", "yahoo!", "slurp")),
)

SCRIPT_UA_MARKERS = (
    "python-requests",
    "python-urllib",
    "httpx/",
    "aiohttp/",
    "curl/",
    "wget/",
    "go-http-client",
)

SERVICE_LABELS = {
    "api": "API",
    "avby-sync": "Парсинг av.by",
    "avby-archive": "Архивация av.by",
    "avby-vin-session": "VIN session",
}


def _normalize_service_name(raw: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "", raw.strip().lower())
    return cleaned[:64]


def _service_display_name(service: str) -> str:
    return SERVICE_LABELS.get(service, service)


def classify_visitor(request: Request) -> dict[str, str]:
    client_header = _normalize_service_name(request.headers.get(INTERNAL_CLIENT_HEADER) or "")
    if client_header:
        return {
            "visitor_label": f"internal:{client_header}",
            "visitor_name": f"Сервис: {_service_display_name(client_header)}",
        }

    user_agent = request.headers.get("user-agent") or ""
    ua_lower = user_agent.lower()

    if ua_lower.startswith(INTERNAL_UA_PREFIX.lower()):
        service = _normalize_service_name(user_agent[len(INTERNAL_UA_PREFIX) :].split()[0])
        if service:
            return {
                "visitor_label": f"internal:{service}",
                "visitor_name": f"Сервис: {_service_display_name(service)}",
            }

    for label, name, patterns in BOT_RULES:
        if any(pattern in ua_lower for pattern in patterns):
            return {"visitor_label": label, "visitor_name": name}

    if any(marker in ua_lower for marker in SCRIPT_UA_MARKERS):
        return {"visitor_label": "tool:script", "visitor_name": "Скрипт (curl/Python)"}

    if "bot" in ua_lower or "spider" in ua_lower or "crawler" in ua_lower:
        return {"visitor_label": "bot:other", "visitor_name": "Другой бот"}

    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    if ip.startswith(("127.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "::1")):
        return {"visitor_label": "internal:network", "visitor_name": f"Внутр. сеть ({ip})"}

    return {"visitor_label": "visitor:anonymous", "visitor_name": "Анонимный посетитель"}


def event_actor_label(*, user_email: str | None, details: dict | None) -> str:
    if user_email:
        return user_email
    if details and details.get("visitor_name"):
        return str(details["visitor_name"])
    return "—"
