"""On-site auto-reply text that depends on the operator's working hours."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings

# Minsk and Moscow share UTC+3 with no DST, so a fixed offset is enough (no tzdata needed).
_TZ = timezone(timedelta(hours=3))


def in_work_hours(now: datetime | None = None) -> bool:
    local = (now or datetime.now(_TZ)).astimezone(_TZ)
    start = int(settings.work_hours_start)
    end = int(settings.work_hours_end)
    return start <= local.hour < end


def lead_reply_hint(now: datetime | None = None) -> str:
    if in_work_hours(now):
        minutes = int(settings.reply_minutes)
        return (
            f"Заявка принята. Ответим в течение {minutes} минут по указанному контакту. "
            "Быстрее — написать нам в Telegram или MAX."
        )
    return (
        f"Заявка принята. Мы на связи ежедневно с {int(settings.work_hours_start)}:00 "
        f"до {int(settings.work_hours_end)}:00 (мск) — ответим утром. "
        "Пока можно написать нам в Telegram или MAX."
    )
