"""CRUD helpers for admin selection-service contracts."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import AdminContract


def _meta_from_payload(payload: dict) -> dict:
    client_name = (
        payload.get("clientCompany")
        if payload.get("clientType") == "legal"
        else payload.get("clientName")
    )
    return {
        "contract_number": (payload.get("contractNumber") or "").strip() or None,
        "client_name": (client_name or "").strip() or None,
        "amount": str(payload.get("amount") or "").strip() or None,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def list_contracts(db: Session, *, limit: int = 500) -> list[AdminContract]:
    return (
        db.query(AdminContract)
        .order_by(desc(AdminContract.updated_at), desc(AdminContract.id))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def get_contract(db: Session, contract_id: int) -> AdminContract | None:
    return db.query(AdminContract).filter(AdminContract.id == contract_id).first()


def create_contract(
    db: Session,
    *,
    payload: dict,
    created_by_id: int | None,
    source_key: str | None = None,
) -> AdminContract:
    meta = _meta_from_payload(payload or {})
    now = datetime.utcnow()
    row = AdminContract(
        contract_number=meta["contract_number"],
        client_name=meta["client_name"],
        amount=meta["amount"],
        payload=meta["payload"],
        source_key=(source_key or "").strip() or None,
        created_by_id=created_by_id,
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_contract(db: Session, row: AdminContract, *, payload: dict) -> AdminContract:
    meta = _meta_from_payload(payload or {})
    row.contract_number = meta["contract_number"]
    row.client_name = meta["client_name"]
    row.amount = meta["amount"]
    row.payload = meta["payload"]
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_contract(db: Session, row: AdminContract) -> None:
    db.delete(row)
    db.commit()


def upsert_imported_contract(
    db: Session,
    *,
    payload: dict,
    source_key: str | None,
    created_by_id: int | None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    contract_number: str | None = None,
    client_name: str | None = None,
    amount: str | None = None,
) -> tuple[AdminContract, bool]:
    """Insert or refresh by source_key. Returns (row, created)."""
    meta = _meta_from_payload(payload or {})
    if contract_number:
        meta["contract_number"] = contract_number.strip() or meta["contract_number"]
    if client_name:
        meta["client_name"] = client_name.strip() or meta["client_name"]
    if amount is not None and str(amount).strip() != "":
        meta["amount"] = str(amount).strip()

    key = (source_key or "").strip() or None
    row = None
    if key:
        row = db.query(AdminContract).filter(AdminContract.source_key == key).first()

    now = datetime.utcnow()
    created = row is None
    if row is None:
        row = AdminContract(
            source_key=key,
            created_by_id=created_by_id,
            created_at=created_at or now,
        )
        db.add(row)

    row.contract_number = meta["contract_number"]
    row.client_name = meta["client_name"]
    row.amount = meta["amount"]
    row.payload = meta["payload"]
    row.updated_at = updated_at or now
    if created_at and row.created_at is None:
        row.created_at = created_at
    db.commit()
    db.refresh(row)
    return row, created


def import_contract_rows(
    db: Session,
    rows: list[dict],
    *,
    created_by_id: int | None,
) -> dict[str, int]:
    created = 0
    updated = 0
    skipped = 0
    for raw in rows:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        payload = raw.get("payload") if isinstance(raw.get("payload"), dict) else raw
        if not isinstance(payload, dict):
            skipped += 1
            continue
        source_key = raw.get("source_key") or raw.get("id")
        _, was_created = upsert_imported_contract(
            db,
            payload=payload,
            source_key=str(source_key) if source_key else None,
            created_by_id=created_by_id,
            created_at=_parse_dt(raw.get("created_at")),
            updated_at=_parse_dt(raw.get("updated_at")),
            contract_number=raw.get("contract_number"),
            client_name=raw.get("client_name"),
            amount=raw.get("amount"),
        )
        if was_created:
            created += 1
        else:
            updated += 1
    return {"created": created, "updated": updated, "skipped": skipped, "total": len(rows)}


def fetch_supabase_contracts(
    *,
    url: str,
    anon_key: str,
    access_token: str | None = None,
) -> list[dict]:
    base = url.strip().rstrip("/")
    key = anon_key.strip()
    if not base or not key:
        raise ValueError("Укажите Project URL и anon key Supabase")
    token = (access_token or "").strip() or key
    endpoint = (
        f"{base}/rest/v1/contracts"
        "?select=id,contract_number,client_name,amount,payload,created_at,updated_at"
        "&order=updated_at.desc"
    )
    req = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise ValueError(f"Supabase HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Не удалось связаться с Supabase: {exc.reason}") from exc

    data = json.loads(body) if body else []
    if not isinstance(data, list):
        raise ValueError("Неожиданный ответ Supabase")
    return data
