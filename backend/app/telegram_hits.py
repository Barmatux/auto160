"""Track TelegramBot hits so we can verify WebpageBot actually reaches the server."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from threading import Lock

_lock = Lock()
_hits: deque[dict[str, str]] = deque(maxlen=30)


def note_telegram_hit(*, path: str, method: str, ip: str | None) -> None:
    with _lock:
        _hits.appendleft(
            {
                "at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                "method": method,
                "path": path[:200],
                "ip": (ip or "-")[:64],
            }
        )


def recent_telegram_hits() -> list[dict[str, str]]:
    with _lock:
        return list(_hits)


def is_telegram_user_agent(user_agent: str | None) -> bool:
    ua = (user_agent or "").lower()
    return "telegrambot" in ua or ua.strip() == "telegram"
