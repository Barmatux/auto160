import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
ALGORITHM = "HS256"
revoked_jti: set[str] = set()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta_minutes: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_delta_minutes)
    to_encode = {
        "sub": subject,
        "exp": expire,
        "type": token_type,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(subject: str) -> str:
    return _create_token(subject=subject, token_type="access", expires_delta_minutes=settings.access_token_expire_minutes)


def create_refresh_token(subject: str) -> str:
    return _create_token(subject=subject, token_type="refresh", expires_delta_minutes=settings.refresh_token_expire_minutes)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])


def revoke_token(token: str) -> bool:
    try:
        payload = decode_token(token)
    except JWTError:
        return False

    jti = payload.get("jti")
    if not jti:
        return False

    revoked_jti.add(jti)
    return True


def is_token_revoked(payload: dict) -> bool:
    jti = payload.get("jti")
    if not jti:
        return False
    return jti in revoked_jti
