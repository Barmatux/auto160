"""SMTP helpers for transactional mail (email verification)."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

logger = logging.getLogger(__name__)


class EmailSendError(RuntimeError):
    pass


def smtp_configured() -> bool:
    return bool((settings.smtp_host or "").strip())


def send_email(*, to: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if not smtp_configured():
        raise EmailSendError("SMTP не настроен (SMTP_HOST пустой)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = (settings.smtp_from or "noreply@auto160.ru").strip()
    msg["To"] = to.strip()
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    host = settings.smtp_host.strip()
    port = int(settings.smtp_port or 587)
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""

    try:
        if settings.smtp_use_tls:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
    except Exception as exc:  # noqa: BLE001 — surface as EmailSendError
        logger.exception("SMTP send failed to=%s subject=%s", to, subject)
        raise EmailSendError(f"Не удалось отправить письмо: {exc}") from exc


def send_verification_email(*, to: str, name: str, verify_url: str) -> None:
    subject = "Подтвердите email на Auto160"
    text_body = (
        f"Здравствуйте, {name}!\n\n"
        f"Чтобы завершить регистрацию на Auto160, подтвердите email:\n{verify_url}\n\n"
        f"Ссылка действует ограниченное время. Если вы не регистрировались — просто игнорируйте письмо.\n"
    )
    html_body = (
        f"<p>Здравствуйте, {name}!</p>"
        f"<p>Чтобы завершить регистрацию на Auto160, подтвердите email:</p>"
        f'<p><a href="{verify_url}">Подтвердить email</a></p>'
        f"<p>Или скопируйте ссылку:<br><code>{verify_url}</code></p>"
        f"<p>Если вы не регистрировались — просто игнорируйте письмо.</p>"
    )
    send_email(to=to, subject=subject, text_body=text_body, html_body=html_body)
