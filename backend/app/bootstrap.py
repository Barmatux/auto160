from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.catalog_seed import seed_catalog_from_csv
from app.config import settings
from app.models import CarListing, ListingStatus, User, UserRole
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


def seed_mock_listings(db: Session) -> None:
    seller = db.query(User).filter(User.role == UserRole.admin).first() or db.query(User).first()
    if not seller:
        return

    mocks = [
        {
            "title": "BMW X1 2019, полный привод, отличное состояние",
            "brand": "BMW",
            "model": "X1",
            "year": 2019,
            "mileage": 86000,
            "price": 27400,
            "city": "Минск",
            "description": "Оригинальный пробег, сервисная история, два ключа. Без ДТП, вложений не требует.",
        },
        {
            "title": "Renault Koleos II рестайлинг 2021",
            "brand": "Renault",
            "model": "Koleos",
            "year": 2021,
            "mileage": 52000,
            "price": 21900,
            "city": "Гродно",
            "description": "Автомобиль из Европы. Комфортная комплектация, камера 360, адаптивный круиз.",
        },
        {
            "title": "Volvo XC60 II 2020 Inscription",
            "brand": "Volvo",
            "model": "XC60",
            "year": 2020,
            "mileage": 64000,
            "price": 36500,
            "city": "Брест",
            "description": "Бережная эксплуатация. Полный пакет ассистентов, кожа, панорама, LED-оптика.",
        },
        {
            "title": "MINI Countryman 2018 Cooper D",
            "brand": "MINI",
            "model": "Countryman",
            "year": 2018,
            "mileage": 98000,
            "price": 18900,
            "city": "Минск",
            "description": "Живой городской кроссовер. Обслужен, чистый салон, два комплекта резины.",
        },
        {
            "title": "Nissan Qashqai II 2018, 1.2T",
            "brand": "Nissan",
            "model": "Qashqai",
            "year": 2018,
            "mileage": 112000,
            "price": 15800,
            "city": "Витебск",
            "description": "Экономичный и комфортный автомобиль для города и трассы. Хорошее состояние.",
        },
    ]

    for payload in mocks:
        exists = db.query(CarListing.id).filter(CarListing.title == payload["title"]).first()
        if exists:
            continue
        listing = CarListing(
            seller_id=seller.id,
            title=payload["title"],
            brand=payload["brand"],
            model=payload["model"],
            year=payload["year"],
            mileage=payload["mileage"],
            price=payload["price"],
            city=payload["city"],
            description=payload["description"],
            status=ListingStatus.published,
        )
        db.add(listing)
    db.commit()


def safe_bootstrap_admin(session_factory, engine) -> None:
    # App may run before migrations in some local flows.
    if not inspect(engine).has_table("users"):
        return

    db = session_factory()
    try:
        ensure_admin_user(db)
        if inspect(engine).has_table("car_listings"):
            seed_mock_listings(db)
        if inspect(engine).has_table("catalog_items"):
            seed_catalog_from_csv(db)
    finally:
        db.close()
