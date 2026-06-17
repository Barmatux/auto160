import re

from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.schemas import LoginRequest, RefreshTokenRequest, RegisterRequest, TokenResponse, UserPublic
from app.security import create_access_token, create_refresh_token, decode_token, hash_password, is_token_revoked, revoke_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _base_username_from_email(email: str) -> str:
    local_part = email.split("@", 1)[0].lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", local_part).strip("_")
    if not normalized:
        normalized = "user"
    return normalized[:60]


def _generate_unique_username(db: Session, email: str) -> str:
    base = _base_username_from_email(email)
    candidate = base
    counter = 1
    while db.query(User.id).filter(func.lower(User.username) == candidate.lower()).first():
        suffix = f"_{counter}"
        candidate = f"{base[: 80 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if payload.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin registration is not allowed")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=_generate_unique_username(db, payload.email),
        email=payload.email,
        name=payload.name,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.username) == payload.login.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid login or password")

    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token type")
    if is_token_revoked(decoded):
        raise HTTPException(status_code=401, detail="Refresh token is revoked")

    email = decoded.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid refresh token subject")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    revoke_token(payload.refresh_token)
    access_token = create_access_token(subject=user.email)
    refresh_token = create_refresh_token(subject=user.email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=400, detail="Authorization Bearer token is required")

    token = authorization.split(" ", 1)[1].strip()
    token_revoked = revoke_token(token)
    return {
        "message": "Logged out",
        "token_revoked": token_revoked,
        "note": "Current implementation uses in-memory token revoke list.",
    }


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
