from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.catalog_seed import seed_catalog_from_csv
from app.config import settings
from app.models import User, UserRole
from app.security import hash_password


def _get_unique_login(db: Session, base_login: str) -> str:
    base = (base_login or "admin").strip().lower()
    candidate = base
    counter = 1
    while db.query(User.id).filter(User.username == candidate).first():
        suffix = f"_{counter}"
        candidate = f"{base[: 80 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def ensure_admin_user(db: Session) -> None:
    if not settings.bootstrap_admin_email or not settings.bootstrap_admin_password:
        return

    existing = db.query(User).filter(User.email == settings.bootstrap_admin_email).first()
    if existing:
        if not existing.username:
            existing.username = _get_unique_login(db, settings.bootstrap_admin_login)
        if existing.role != UserRole.admin:
            existing.role = UserRole.admin
        db.commit()
        return

    admin = User(
        username=_get_unique_login(db, settings.bootstrap_admin_login),
        email=settings.bootstrap_admin_email,
        name=settings.bootstrap_admin_name,
        role=UserRole.admin,
        password_hash=hash_password(settings.bootstrap_admin_password),
    )
    db.add(admin)
    db.commit()


def safe_bootstrap_admin(session_factory, engine) -> None:
    # App may run before migrations in some local flows.
    if not inspect(engine).has_table("users"):
        return

    db = session_factory()
    try:
        ensure_admin_user(db)
        if inspect(engine).has_table("catalog_items"):
            seed_catalog_from_csv(db)
    finally:
        db.close()
