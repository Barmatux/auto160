"""Manager alerts for new public leads (Telegram bot and/or e-mail).

Runs in a FastAPI background task; never raises, so a broken channel cannot
block a customer's form submission.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings
from app.db import SessionLocal
from app.email_smtp import EmailSendError, send_email, smtp_configured
from app.models import Message, MessageThread, SiteLead

logger = logging.getLogger(__name__)

_SOURCE_LABELS = {
    "belarus_landing": "Заявка на подбор (/by)",
    "belarus_consultation": "Консультация по ссылке av.by",
    "featured_modal": "Карточка в подборке",
    "site_chat": "Чат на сайте",
    "inspection_customs_retry": "Проверка ГТК (ждёт ответ)",
}


def _lead_text(lead: SiteLead) -> str:
    lines = [
        "Новая заявка Auto160",
        f"Источник: {_SOURCE_LABELS.get(lead.source, lead.source)}",
        f"Имя: {lead.contact_name}",
        f"Контакт: {lead.contact}",
    ]
    if lead.comment:
        lines.append(f"Комментарий: {lead.comment[:700]}")
    if lead.avby_url:
        lines.append(f"Ссылка: {lead.avby_url}")
    if lead.consent_marketing:
        lines.append("Согласие на информационные сообщения: да")
    lines.append("Все заявки: https://auto160.ru/admin/site-leads")
    return "\n".join(lines)


def _send_telegram(text: str) -> None:
    token = (settings.telegram_bot_token or "").strip()
    chat_id = (settings.lead_telegram_chat_id or "").strip()
    if not token or not chat_id:
        return
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.warning("Lead Telegram alert failed: HTTP %s %s", resp.status_code, resp.text[:200])
    except Exception:  # noqa: BLE001 — alerts are best effort
        logger.exception("Lead Telegram alert failed")


def _send_email(text: str) -> None:
    to = (settings.lead_notify_email or "").strip()
    if not to or not smtp_configured():
        return
    try:
        send_email(to=to, subject="Новая заявка Auto160", text_body=text)
    except EmailSendError:
        logger.warning("Lead e-mail alert failed", exc_info=True)


def notify_new_lead(lead_id: int) -> None:
    """Send configured alerts for a stored lead. Safe to call from a background task."""
    try:
        with SessionLocal() as db:
            lead = db.get(SiteLead, lead_id)
            if lead is None:
                return
            text = _lead_text(lead)
        _send_telegram(text)
        _send_email(text)
    except Exception:  # noqa: BLE001
        logger.exception("notify_new_lead failed lead_id=%s", lead_id)


def notify_new_thread_message(thread_id: int, message_id: int) -> None:
    """Alert managers about a visitor message on a listing chat. Best effort."""
    try:
        with SessionLocal() as db:
            thread = db.get(MessageThread, thread_id)
            msg = db.get(Message, message_id)
            if thread is None or msg is None:
                return
            listing_title = getattr(thread.listing, "title", None) or f"объявление #{thread.listing_id}"
            text = "\n".join(
                [
                    "Новое сообщение в чате Auto160",
                    f"Авто: {listing_title}",
                    f"Имя: {thread.contact_name}",
                    f"Телефон: {thread.contact_phone}",
                    f"Сообщение: {msg.body[:700]}",
                    "Ответить: https://auto160.ru/admin/messages",
                ]
            )
        _send_telegram(text)
        _send_email(text)
    except Exception:  # noqa: BLE001
        logger.exception("notify_new_thread_message failed thread_id=%s", thread_id)
