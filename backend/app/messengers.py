"""Public messenger links for header / contact CTAs."""

from __future__ import annotations

from urllib.parse import quote

from app.config import settings

# Keep in sync with messenger_widget.js / listing_detail contact row.
MESSENGER_TELEGRAM_URL = "https://t.me/auto160"
MESSENGER_MAX_URL = (
    "https://max.ru/u/f9LHodD0cOIUwILxPw-KsvA1_CDFtdhIMz2oMtYa_gELW9HMhq7_whWwjSw"
)
# Digits only, international without "+". Set WHATSAPP_PHONE in .env.vm; empty hides WhatsApp.
MESSENGER_WHATSAPP_PHONE = (settings.whatsapp_phone or "").strip()

DEFAULT_CTA_TEXT = "Здравствуйте! Хочу подобрать авто. Бюджет: … Марка/модель: …"


def messenger_whatsapp_url() -> str | None:
    phone = "".join(ch for ch in MESSENGER_WHATSAPP_PHONE if ch.isdigit())
    if len(phone) < 11:
        return None
    return f"https://wa.me/{phone}"


def header_messenger_links() -> list[dict[str, str]]:
    """Messengers that are actually reachable (WhatsApp appears once a number is set)."""
    links = [
        {"id": "max", "label": "MAX", "url": MESSENGER_MAX_URL},
        {"id": "telegram", "label": "Telegram", "url": MESSENGER_TELEGRAM_URL},
    ]
    wa = messenger_whatsapp_url()
    if wa:
        links.append({"id": "whatsapp", "label": "WhatsApp", "url": wa})
    return links


def messenger_prefill_url(url: str, messenger_id: str, text: str | None = None) -> str:
    """Add a ready-made first message where the messenger supports it."""
    message = (text or DEFAULT_CTA_TEXT).strip()
    if messenger_id in {"telegram", "whatsapp"} and url and url != "#":
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}text={quote(message)}"
    return url
