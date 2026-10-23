"""Public messenger links for header / contact CTAs."""

from __future__ import annotations

# Keep in sync with messenger_widget.js / listing_detail contact row.
MESSENGER_TELEGRAM_URL = "https://t.me/auto160"
MESSENGER_MAX_URL = (
    "https://max.ru/u/f9LHodD0cOIUwILxPw-KsvA1_CDFtdhIMz2oMtYa_gELW9HMhq7_whWwjSw"
)
# Digits only, international without +. Empty until business WhatsApp is confirmed.
MESSENGER_WHATSAPP_PHONE = ""


def messenger_whatsapp_url() -> str | None:
    phone = "".join(ch for ch in MESSENGER_WHATSAPP_PHONE if ch.isdigit())
    if len(phone) < 11:
        return None
    return f"https://wa.me/{phone}"


def header_messenger_links() -> list[dict[str, str]]:
    links = [
        {"id": "max", "label": "MAX", "url": MESSENGER_MAX_URL},
        {"id": "telegram", "label": "Telegram", "url": MESSENGER_TELEGRAM_URL},
        {
            "id": "whatsapp",
            "label": "WhatsApp",
            # Fill MESSENGER_WHATSAPP_PHONE to enable a real chat link.
            "url": messenger_whatsapp_url() or "#",
        },
    ]
    return links
