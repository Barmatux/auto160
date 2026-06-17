from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_admin
from app.models import User
from app.schemas import UserPublic, UserRoleUpdateRequest

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

    # Prevent removing the last admin from current actor implicitly.
    if target_user.id == current_admin.id and payload.role != target_user.role:
        raise HTTPException(status_code=400, detail="Use another admin to change your own role")

    target_user.role = payload.role
    db.commit()
    db.refresh(target_user)
    return target_user
