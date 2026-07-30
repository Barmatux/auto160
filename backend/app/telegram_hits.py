"""Track crawler hits on OG debug endpoints."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import Lock

_lock = Lock()
_hits: deque[dict[str, str]] = deque(maxlen=50)


def note_hit(
    *,
    path: str,
    method: str,
    ip: str | None,
    user_agent: str | None,
    kind: str,
) -> None:
    with _lock:
        _hits.appendleft(
            {
                "at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "kind": kind,
                "method": method,
                "path": path[:200],
                "ip": (ip or "-")[:64],
                "ua": ((user_agent or "-").replace("<", ""))[:160],
            }
        )


def recent_hits() -> list[dict[str, str]]:
    with _lock:
        return list(_hits)


def classify_user_agent(user_agent: str | None) -> str | None:
    ua = (user_agent or "").lower()
    if not ua:
        return "empty-ua"
    if "telegrambot" in ua or ua.strip() == "telegram":
        return "telegram"
    if any(x in ua for x in ("bot", "crawl", "spider", "preview", "slurp", "facebook", "whatsapp")):
        return "bot"
    return None


def is_telegram_user_agent(user_agent: str | None) -> bool:
    return classify_user_agent(user_agent) == "telegram"
