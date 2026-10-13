from email.utils import parseaddr

from app.email_smtp import _message_id_domain, send_email


def test_message_id_domain_from_display_name():
    assert _message_id_domain("Auto160 <noreply@auto160.ru>") == "auto160.ru"


def test_send_email_sets_message_id_and_date(monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            return None

        def login(self, user, password):
            return None

        def send_message(self, msg):
            captured["msg"] = msg

    monkeypatch.setattr("app.email_smtp.smtp_configured", lambda: True)
    monkeypatch.setattr("app.email_smtp.settings.smtp_host", "smtp.example")
    monkeypatch.setattr("app.email_smtp.settings.smtp_port", 465)
    monkeypatch.setattr("app.email_smtp.settings.smtp_user", "noreply@auto160.ru")
    monkeypatch.setattr("app.email_smtp.settings.smtp_password", "x")
    monkeypatch.setattr("app.email_smtp.settings.smtp_from", "Auto160 <noreply@auto160.ru>")
    monkeypatch.setattr("app.email_smtp.settings.smtp_use_ssl", True)
    monkeypatch.setattr("app.email_smtp.settings.smtp_use_tls", False)
    monkeypatch.setattr("app.email_smtp.smtplib.SMTP_SSL", FakeSMTP)

    send_email(to="user@example.com", subject="Test", text_body="hi")
    msg = captured["msg"]
    assert msg["Message-ID"]
    assert "@auto160.ru>" in msg["Message-ID"]
    assert msg["Date"]
    assert parseaddr(msg["From"])[1] == "noreply@auto160.ru"
