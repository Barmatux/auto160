from __future__ import annotations

import json
from datetime import datetime
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


def _parse_registered_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00").replace("+00:00", ""))
    except ValueError:
        return None


def account_payload_from_dict(data: dict[str, Any]) -> dict[str, Any]:
    status = (data.get("status") or "pending").strip()
    is_active = status == "confirmed" and bool(data.get("api_key"))
    if "is_active" in data:
        is_active = bool(data["is_active"])
    return {
        "email": (data.get("email") or "").strip().lower(),
        "name": (data.get("name") or "").strip(),
        "mailtm_password": data.get("mailtm_password"),
        "avby_password": data.get("avby_password"),
        "api_key": data.get("api_key"),
        "auth_token": data.get("auth_token"),
        "email_token": data.get("email_token"),
        "status": status,
        "is_active": is_active,
        "error_message": data.get("error"),
        "registered_at": _parse_registered_at(data.get("created_at")),
    }


def upsert_avby_service_account(db: Session, data: dict[str, Any]) -> AvbyServiceAccount:
    payload = account_payload_from_dict(data)
    email = payload.pop("email")
    if not email:
        raise ValueError("Account email is required")

    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.email == email).first()
    if account is None:
        account = AvbyServiceAccount(email=email, **payload)
        db.add(account)
    else:
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
        if not isinstance(row, dict) or not row.get("email"):
            skipped += 1
            continue
        upsert_avby_service_account(db, row)
        imported += 1
    return {"imported": imported, "skipped": skipped, "path": str(path)}


def serialize_account_public(account: AvbyServiceAccount) -> dict[str, Any]:
    return {
        "id": account.id,
        "email": account.email,
        "name": account.name,
        "status": account.status,
        "is_active": account.is_active,
        "api_key_masked": mask_secret(account.api_key),
        "has_auth_token": bool(account.auth_token),
        "error_message": account.error_message,
        "notes": account.notes,
        "registered_at": account.registered_at,
        "created_at": account.created_at,
    }


def serialize_account_secrets(account: AvbyServiceAccount) -> dict[str, Any]:
    data = serialize_account_public(account)
    data.update(
        {
            "mailtm_password": account.mailtm_password,
            "avby_password": account.avby_password,
            "api_key": account.api_key,
            "auth_token": account.auth_token,
            "email_token": account.email_token,
        }
    )
    return data
