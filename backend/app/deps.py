from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserRole
from app.security import decode_token, is_token_revoked

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or is_token_revoked(payload):
            raise credentials_exception
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception from None

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise credentials_exception
    return user


def require_seller_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in {UserRole.seller, UserRole.admin}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def get_optional_current_user(
    token: str | None = Depends(oauth2_optional_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access" or is_token_revoked(payload):
            return None
        email = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None

    return db.query(User).filter(User.email == email).first()
