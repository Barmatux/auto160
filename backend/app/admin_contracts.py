"""CRUD helpers for admin selection-service contracts."""

from __future__ import annotations

from datetime import datetime

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


def list_contracts(db: Session, *, limit: int = 500) -> list[AdminContract]:
    return (
        db.query(AdminContract)
        .order_by(desc(AdminContract.updated_at), desc(AdminContract.id))
        .limit(max(1, min(limit, 1000)))
        .all()
    )


def get_contract(db: Session, contract_id: int) -> AdminContract | None:
    return db.query(AdminContract).filter(AdminContract.id == contract_id).first()


def create_contract(db: Session, *, payload: dict, created_by_id: int | None) -> AdminContract:
    meta = _meta_from_payload(payload or {})
    now = datetime.utcnow()
    row = AdminContract(
        contract_number=meta["contract_number"],
        client_name=meta["client_name"],
        amount=meta["amount"],
        payload=meta["payload"],
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
