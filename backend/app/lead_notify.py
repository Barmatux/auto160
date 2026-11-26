"""Manager alerts for new public leads and site-chat messages (Telegram bot and/or e-mail).

Runs in FastAPI background tasks; never raises, so a broken channel cannot block a
customer's form submission.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.db import SessionLocal
from app.email_smtp import EmailSendError, send_email, smtp_configured
from app.models import Message, MessageThread, SiteLead
from app.telegram_bridge import lead_keyboard, send_alert, site_base, thread_keyboard

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
        "🆕 Новая заявка Auto160",
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
    lines.append("")
    lines.append("Ответ (Reply) на это сообщение сохранится заметкой к заявке.")
    return "\n".join(lines)


def _send_email(subject: str, text: str) -> None:
    to = (settings.lead_notify_email or "").strip()
    if not to or not smtp_configured():
        return
    try:
        send_email(to=to, subject=subject, text_body=text)
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
            keyboard = lead_keyboard(lead)
        send_alert(text, kind="lead", ref_id=lead_id, reply_markup=keyboard)
        _send_email("Новая заявка Auto160", f"{text}\n\nВсе заявки: {site_base()}/admin/site-leads")
    except Exception:  # noqa: BLE001
        logger.exception("notify_new_lead failed lead_id=%s", lead_id)


def notify_new_thread_message(thread_id: int, message_id: int) -> None:
    """Alert the operator about a visitor message in a listing chat. Best effort."""
    try:
        with SessionLocal() as db:
            thread = db.get(MessageThread, thread_id)
            msg = db.get(Message, message_id)
            if thread is None or msg is None:
                return
            listing_title = getattr(thread.listing, "title", None) or f"объявление #{thread.listing_id}"
            text = "\n".join(
                [
                    "💬 Сообщение в чате на сайте",
                    f"Авто: {listing_title}",
                    f"Имя: {thread.contact_name}",
                    f"Телефон: {thread.contact_phone}",
                    "",
                    msg.body[:700],
                    "",
                    "Ответ (Reply) на это сообщение уйдёт клиенту в чат на сайте.",
                ]
            )
        send_alert(text, kind="thread", ref_id=thread_id, reply_markup=thread_keyboard())
        _send_email(
            "Сообщение в чате Auto160",
            f"{text}\n\nОтветить: {site_base()}/admin/messages",
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_new_thread_message failed thread_id=%s", thread_id)
