from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.avby_accounts import import_avby_accounts_from_json, serialize_account_public, serialize_account_secrets
from app.db import get_db
from app.deps import require_admin
from app.models import AvbyServiceAccount, User
from app.schemas import (
    AvbyAccountsImportResult,
    AvbyServiceAccountPublic,
    AvbyServiceAccountSecrets,
    AvbyServiceAccountUpdateRequest,
    UserPublic,
    UserRoleUpdateRequest,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/users", response_model=list[UserPublic])
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/users/{user_id}/role", response_model=UserPublic)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == current_admin.id and payload.role != target_user.role:
        raise HTTPException(status_code=400, detail="Use another admin to change your own role")

    target_user.role = payload.role
    db.commit()
    db.refresh(target_user)
    return target_user


@router.get("/avby-accounts", response_model=list[AvbyServiceAccountPublic])
def list_avby_accounts(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    accounts = db.query(AvbyServiceAccount).order_by(AvbyServiceAccount.created_at.desc()).all()
    return [serialize_account_public(account) for account in accounts]


@router.get("/avby-accounts/{account_id}/secrets", response_model=AvbyServiceAccountSecrets)
def get_avby_account_secrets(
    account_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return serialize_account_secrets(account)


@router.post("/avby-accounts/import-json", response_model=AvbyAccountsImportResult)
def import_avby_accounts_json(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        result = import_avby_accounts_from_json(db)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return result


@router.patch("/avby-accounts/{account_id}", response_model=AvbyServiceAccountPublic)
def update_avby_account(
    account_id: int,
    payload: AvbyServiceAccountUpdateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if payload.is_active is not None:
        account.is_active = payload.is_active
    if payload.notes is not None:
        account.notes = payload.notes.strip() or None
    db.commit()
    db.refresh(account)
    return serialize_account_public(account)


@router.delete("/avby-accounts/{account_id}")
def delete_avby_account(
    account_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    account = db.query(AvbyServiceAccount).filter(AvbyServiceAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
    return {"ok": True}
