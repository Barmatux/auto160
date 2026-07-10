from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AvbyServiceAccount


def mask_secret(value: str | None, visible: int = 4) -> str | None:
    if not value:
        return None
    if len(value) <= visible * 2:
        return "*" * len(value)
    return f"{value[:visible]}…{value[-visible:]}"


def normalize_avby_phone(raw: str | None) -> str | None:
    """Normalize Belarus mobile to 9 national digits (e.g. 291234567)."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if digits.startswith("375"):
        digits = digits[3:]
    if len(digits) != 9:
        raise ValueError(f"Expected 9-digit BY number, got: {raw!r}")
    return digits


def format_avby_phone_display(national: str | None) -> str | None:
    if not national:
        return None
    return f"+375{national}"


def avby_login_identifier(account: AvbyServiceAccount) -> str:
    if account.phone:
        return format_avby_phone_display(account.phone) or account.phone
    if account.email:
        return account.email.strip()
    raise ValueError("Account has no email or phone for av.by login")


def account_display_login(account: AvbyServiceAccount) -> str:
    if account.phone:
        return format_avby_phone_display(account.phone) or account.phone
    return account.email or "—"


def _parse_registered_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def account_payload_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    status = (data.get("status") or "pending").strip()
    is_active = status in {"confirmed", "phone_verified"} and bool(data.get("api_key"))
    if "is_active" in data:
        is_active = bool(data["is_active"])
    payload = {
        "name": (data.get("name") or "").strip(),
        "mailtm_password": data.get("mailtm_password"),
        "avby_password": data.get("avby_password"),
        "api_key": data.get("api_key"),
        "auth_token": data.get("auth_token"),
        "refresh_token": data.get("refresh_token"),
        "auth_token_expires_at": data.get("auth_token_expires_at"),
        "email_token": data.get("email_token"),
        "status": status,
        "is_active": is_active,
        "error_message": data.get("error"),
        "notes": data.get("notes"),
        "registered_at": _parse_registered_at(data.get("created_at")),
    }
    if data.get("purpose"):
        payload["purpose"] = data["purpose"]
    if data.get("daily_vin_limit") is not None:
        payload["daily_vin_limit"] = int(data["daily_vin_limit"])
    if data.get("vin_checks_today") is not None:
        payload["vin_checks_today"] = int(data["vin_checks_today"])
    if data.get("vin_checks_day"):
        payload["vin_checks_day"] = date.fromisoformat(str(data["vin_checks_day"]))
    if data.get("phone"):
        payload["phone"] = normalize_avby_phone(str(data["phone"]))
    return {"email": (data.get("email") or "").strip().lower() or None, **payload}


def upsert_avby_service_account(db: Session, data: dict[str, Any]) -> AvbyServiceAccount:
    payload = account_payload_from_dict(data)
    email = payload.pop("email", None)
    phone = payload.pop("phone", None)
    if not email and not phone:
        raise ValueError("Account email or phone is required")

    account = None
    if email:
        account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == email).first()
    if account is None and phone:
        account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.phone == phone).first()
    if account is None:
        account = AvbyServiceAccount(email=email, phone=phone, **payload)
        db.add(account)
    else:
        if email:
            account.email = email
        if phone:
            account.phone = phone
        for field, value in payload.items():
            if value is not None and value != "":
                setattr(account, field, value)
        account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return account


def import_avby_accounts_from_json(db: Session, json_path: Path | None = None) -> dict[str, int]:
    path = json_path or Path(settings.avby_accounts_json_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise FileNotFoundError(f"Accounts JSON not found: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("accounts") or []
    imported = 0
    skipped = 0
    for row in rows:
        if not isinstance(row, dict) or (not row.get("email") and not row.get("phone")):
            skipped += 1
            continue
        upsert_avby_service_account(db, row)
        imported += 1
    return {"imported": imported, "skipped": skipped, "path": str(path)}


def serialize_account_public(account: AvbyServiceAccount) -> dict[str, Any]:
    reset_vin_checks_if_needed(account)
    return {
        "id": account.id,
        "email": account.email,
        "phone": account.phone,
        "phone_display": format_avby_phone_display(account.phone),
        "login": account_display_login(account),
        "name": account.name,
        "status": account.status,
        "purpose": account.purpose,
        "daily_vin_limit": account.daily_vin_limit,
        "vin_checks_today": account.vin_checks_today,
        "vin_checks_remaining": vin_checks_remaining(account),
        "is_active": account.is_active,
        "api_key_masked": mask_secret(account.api_key),
        "has_auth_token": bool(account.auth_token),
        "has_refresh_token": bool(account.refresh_token),
        "error_message": account.error_message,
        "notes": account.notes,
        "registered_at": account.registered_at,
        "created_at": account.created_at,
    }


VIN_TEST_DAILY_LIMIT = 30


def reset_vin_checks_if_needed(account: AvbyServiceAccount, *, today: date | None = None) -> None:
    current_day = today or date.today()
    if account.vin_checks_day != current_day:
        account.vin_checks_today = 0
        account.vin_checks_day = current_day


def vin_checks_remaining(account: AvbyServiceAccount) -> int | None:
    if account.daily_vin_limit is None:
        return None
    reset_vin_checks_if_needed(account)
    return max(0, account.daily_vin_limit - account.vin_checks_today)


def can_consume_vin_check(account: AvbyServiceAccount) -> bool:
    remaining = vin_checks_remaining(account)
    if remaining is None:
        return True
    return remaining > 0


def consume_vin_check(db: Session, account: AvbyServiceAccount) -> bool:
    if not can_consume_vin_check(account):
        return False
    if account.daily_vin_limit is not None:
        reset_vin_checks_if_needed(account)
        account.vin_checks_today += 1
        account.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(account)
    return True


VIN_ACCOUNT_STATUSES = ("confirmed", "phone_verified")


def list_active_vin_accounts(db: Session) -> list[AvbyServiceAccount]:
    rows = (
        db.query(AvbyServiceAccount)
        .filter(
            AvbyServiceAccount.purpose == "vin_test",
            AvbyServiceAccount.is_active.is_(True),
            AvbyServiceAccount.status.in_(VIN_ACCOUNT_STATUSES),
            AvbyServiceAccount.api_key.isnot(None),
        )
        .order_by(AvbyServiceAccount.vin_checks_today.asc(), AvbyServiceAccount.id.asc())
        .all()
    )
    return [account for account in rows if can_consume_vin_check(account)]


def select_vin_account(db: Session, *, exclude_ids: set[int] | None = None) -> AvbyServiceAccount | None:
    excluded = exclude_ids or set()
    for account in list_active_vin_accounts(db):
        if account.id not in excluded:
            return account
    return None


def list_vin_accounts_for_keepalive(db: Session) -> list[AvbyServiceAccount]:
    return (
        db.query(AvbyServiceAccount)
        .filter(
            AvbyServiceAccount.purpose == "vin_test",
            AvbyServiceAccount.is_active.is_(True),
            AvbyServiceAccount.status.in_(VIN_ACCOUNT_STATUSES),
        )
        .order_by(AvbyServiceAccount.id.asc())
        .all()
    )


def get_vin_test_account(db: Session) -> AvbyServiceAccount | None:
    """Pick next account from the active VIN pool (lowest usage first)."""
    return select_vin_account(db)


def serialize_account_secrets(account: AvbyServiceAccount) -> dict[str, Any]:
    data = serialize_account_public(account)
    data.update(
        {
            "mailtm_password": account.mailtm_password,
            "avby_password": account.avby_password,
            "api_key": account.api_key,
            "auth_token": account.auth_token,
            "refresh_token": account.refresh_token,
            "email_token": account.email_token,
        }
    )
    return data
