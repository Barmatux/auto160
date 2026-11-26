"""Telegram bot bridge for the single operator.

Outgoing: every new lead / site-chat message is sent to the operator chat with action buttons.
Incoming (webhook):
  * Reply to a *chat* alert  → the text is posted to the visitor's chat on the site.
  * Reply to a *lead* alert  → the text is saved as a note on the lead.
  * Buttons under a lead     → change the funnel status.
Everything is best effort and never raises into request handling.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Message, MessageSender, MessageThread, MessageThreadStatus, SiteLead, TelegramMessageLink

logger = logging.getLogger(__name__)

SITE_FALLBACK = "https://auto160.ru"

# Funnel: which statuses can be reached from the current one (buttons under the alert).
_NEXT_STATUS: dict[str, list[str]] = {
    "new": ["contacted", "lost"],
    "contacted": ["deposit", "bought", "lost"],
    "deposit": ["bought", "lost"],
    "bought": ["delivered"],
    "delivered": [],
    "lost": ["contacted"],
}
_BUTTON_LABELS = {
    "contacted": "✅ Взял в работу",
    "deposit": "💰 Задаток",
    "bought": "🚗 Куплено",
    "delivered": "📦 Доставлено",
    "lost": "✖ Отказ",
}
_STATUS_LABELS = {
    "new": "Новая",
    "contacted": "На связи",
    "deposit": "Задаток",
    "bought": "Куплено",
    "delivered": "Доставлено",
    "lost": "Отказ",
}


def site_base() -> str:
    return (settings.public_site_url or "").strip().rstrip("/") or SITE_FALLBACK


def token_set() -> bool:
    return bool((settings.telegram_bot_token or "").strip())


def bot_enabled() -> bool:
    return bool((settings.telegram_bot_token or "").strip() and (settings.lead_telegram_chat_id or "").strip())


def webhook_secret() -> str:
    configured = (settings.telegram_webhook_secret or "").strip()
    if configured:
        return configured
    token = (settings.telegram_bot_token or "").strip()
    return hashlib.sha256(f"auto160-tg:{token}".encode()).hexdigest()[:48]


def _call(method: str, payload: dict) -> dict | None:
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        return None
    try:
        resp = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=10)
        data = resp.json()
        if not data.get("ok"):
            logger.warning("Telegram %s failed: %s", method, str(data)[:300])
            return None
        return data.get("result")
    except Exception:  # noqa: BLE001
        logger.exception("Telegram %s failed", method)
        return None


def register_webhook() -> None:
    """Point the bot at this site (idempotent). Called once at startup.

    Needs only the token: /start must work before LEAD_TELEGRAM_CHAT_ID is known.
    """
    if not token_set():
        return
    result = _call(
        "setWebhook",
        {
            "url": f"{site_base()}/api/v1/telegram/webhook",
            "secret_token": webhook_secret(),
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False,
        },
    )
    if result is not None:
        logger.info("Telegram webhook registered at %s", site_base())


# ── keyboards ────────────────────────────────────────────────────────────────


def _contact_buttons(contact: str) -> list[dict]:
    value = (contact or "").strip()
    buttons: list[dict] = []
    match = re.search(r"(?:t\.me/|@)([A-Za-z0-9_]{4,32})", value)
    if match:
        buttons.append({"text": "✈️ Написать в Telegram", "url": f"https://t.me/{match.group(1)}"})
    else:
        digits = re.sub(r"\D", "", value)
        if len(digits) == 11 and digits.startswith("8"):
            digits = "7" + digits[1:]
        if len(digits) >= 10:
            buttons.append({"text": "💬 WhatsApp", "url": f"https://wa.me/{digits}"})
    return buttons


def lead_keyboard(lead: SiteLead) -> dict:
    rows: list[list[dict]] = []
    contact = _contact_buttons(lead.contact)
    if contact:
        rows.append(contact)
    steps = [
        {"text": _BUTTON_LABELS[s], "callback_data": f"lead:{lead.id}:{s}"}
        for s in _NEXT_STATUS.get(lead.status, [])
    ]
    if steps:
        rows.append(steps)
    rows.append([{"text": "Открыть в админке", "url": f"{site_base()}/admin/site-leads?id={lead.id}"}])
    return {"inline_keyboard": rows}


def thread_keyboard() -> dict:
    return {"inline_keyboard": [[{"text": "Открыть чат в админке", "url": f"{site_base()}/admin/messages"}]]}


# ── outgoing ─────────────────────────────────────────────────────────────────


def send_alert(text: str, *, kind: str, ref_id: int, reply_markup: dict | None = None) -> None:
    """Send an alert to the operator chat and remember which lead/thread it belongs to."""
    if not bot_enabled():
        return
    chat_id = settings.lead_telegram_chat_id.strip()
    payload: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _call("sendMessage", payload)
    if not result:
        return
    try:
        with SessionLocal() as db:
            db.add(
                TelegramMessageLink(
                    chat_id=chat_id,
                    tg_message_id=int(result["message_id"]),
                    kind=kind,
                    ref_id=ref_id,
                )
            )
            db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Could not store Telegram message link")


def _reply(chat_id: str | int, text: str, reply_to: int | None = None) -> None:
    payload: dict = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
        payload["allow_sending_without_reply"] = True
    _call("sendMessage", payload)


# ── incoming ─────────────────────────────────────────────────────────────────


def _is_operator_chat(chat_id: int | str | None) -> bool:
    return str(chat_id or "") == (settings.lead_telegram_chat_id or "").strip() != ""


def _handle_callback(db: Session, query: dict) -> None:
    message = query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    qid = query.get("id")
    if not _is_operator_chat(chat_id):
        _call("answerCallbackQuery", {"callback_query_id": qid, "text": "Нет доступа"})
        return
    parts = str(query.get("data") or "").split(":")
    if len(parts) != 3 or parts[0] != "lead" or not parts[1].isdigit():
        _call("answerCallbackQuery", {"callback_query_id": qid})
        return
    # Local import: featured imports a lot and we avoid cycles at module load.
    from app.featured import set_lead_status

    try:
        lead = set_lead_status(db, int(parts[1]), parts[2])
    except ValueError as exc:
        _call("answerCallbackQuery", {"callback_query_id": qid, "text": str(exc)[:150]})
        return
    _call(
        "answerCallbackQuery",
        {"callback_query_id": qid, "text": f"Статус: {_STATUS_LABELS.get(lead.status, lead.status)}"},
    )
    base_text = str(message.get("text") or "").split("\n\nСтатус:")[0]
    _call(
        "editMessageText",
        {
            "chat_id": chat_id,
            "message_id": message.get("message_id"),
            "text": f"{base_text}\n\nСтатус: {_STATUS_LABELS.get(lead.status, lead.status)}",
            "disable_web_page_preview": True,
            "reply_markup": lead_keyboard(lead),
        },
    )


def _handle_message(db: Session, message: dict) -> None:
    chat_id = (message.get("chat") or {}).get("id")
    text = str(message.get("text") or "").strip()
    message_id = message.get("message_id")
    if text.startswith("/start") or text.startswith("/id"):
        _reply(
            chat_id,
            f"Ваш chat_id: {chat_id}\n"
            + (
                "Этот чат подключён: сюда приходят заявки и сообщения с сайта."
                if _is_operator_chat(chat_id)
                else "Укажите это число в LEAD_TELEGRAM_CHAT_ID в .env.vm и перезапустите API."
            ),
        )
        return
    if not _is_operator_chat(chat_id) or not text:
        return
    replied = message.get("reply_to_message") or {}
    link = None
    if replied.get("message_id"):
        link = (
            db.query(TelegramMessageLink)
            .filter(
                TelegramMessageLink.chat_id == str(chat_id),
                TelegramMessageLink.tg_message_id == int(replied["message_id"]),
            )
            .first()
        )
    if link is None:
        _reply(
            chat_id,
            "Чтобы ответить клиенту, нажмите «Ответить» (Reply) на сообщение о заявке или о чате.",
            reply_to=message_id,
        )
        return
    if link.kind == "thread":
        thread = db.get(MessageThread, link.ref_id)
        if thread is None:
            _reply(chat_id, "Диалог не найден (удалён?).", reply_to=message_id)
            return
        now = datetime.utcnow()
        db.add(
            Message(
                thread_id=thread.id,
                sender=MessageSender.manager,
                sender_user_id=None,
                body=text[:4000],
                created_at=now,
            )
        )
        thread.last_message_at = now
        thread.manager_last_read_at = now
        thread.status = MessageThreadStatus.open
        db.commit()
        _reply(chat_id, "✓ Отправлено клиенту в чат на сайте.", reply_to=message_id)
        return
    if link.kind == "lead":
        from app.featured import append_lead_note

        try:
            append_lead_note(db, link.ref_id, text)
        except ValueError as exc:
            _reply(chat_id, str(exc), reply_to=message_id)
            return
        _reply(chat_id, "📝 Заметка добавлена к заявке.", reply_to=message_id)


def handle_update(db: Session, update: dict) -> None:
    try:
        if update.get("callback_query"):
            _handle_callback(db, update["callback_query"])
        elif update.get("message"):
            _handle_message(db, update["message"])
    except Exception:  # noqa: BLE001
        logger.exception("Telegram update handling failed")
        db.rollback()
