import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class UserRole(str, enum.Enum):
    guest = "guest"
    seller = "seller"
    admin = "admin"


class ListingStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.seller, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listings: Mapped[list["CarListing"]] = relationship(back_populates="seller")


class CarListing(Base):
    __tablename__ = "car_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    avby_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, unique=True)
    brand: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    generation: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(Numeric(12, 2), index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    body_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    drive_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    transmission_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    engine_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    engine_capacity_l: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    engine_power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vin_indicated: Mapped[bool | None] = mapped_column(nullable=True)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    vin_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seller_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_photos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.draft, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    seller: Mapped[User] = relationship(back_populates="listings")


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    make: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    generation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year_from: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    year_to: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    min_price_rub: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    body_type: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    export_country: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    steering_wheel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    engine_power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_volume_l: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    drivetrain: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_site: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    raw_specs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rating: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    photos: Mapped[list["CatalogItemPhoto"]] = relationship(back_populates="catalog_item", cascade="all, delete-orphan")


class AvbySyncRun(Base):
    __tablename__ = "avby_sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", index=True)
    trigger: Mapped[str] = mapped_column(String(30), default="manual", index=True)
    models_count: Mapped[int] = mapped_column(Integer, default=0)
    brands_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_by_hp_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_brands_count: Mapped[int] = mapped_column(Integer, default=0)
    pages_fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    max_hp: Mapped[int] = mapped_column(Integer, default=160)
    dry_run: Mapped[bool] = mapped_column(default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class AvbyServiceAccount(Base):
    __tablename__ = "avby_service_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(120), default="")
    mailtm_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avby_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    auth_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    purpose: Mapped[str] = mapped_column(String(30), default="parser", index=True)
    daily_vin_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vin_checks_today: Mapped[int] = mapped_column(Integer, default=0)
    vin_checks_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CatalogItemPhoto(Base):
    __tablename__ = "catalog_item_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    content_type: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_cover: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    catalog_item: Mapped[CatalogItem] = relationship(back_populates="photos")


class SiteEvent(Base):
    __tablename__ = "site_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500), index=True)
    query_string: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class VinCustomsCheck(Base):
    __tablename__ = "vin_customs_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vin: Mapped[str] = mapped_column(String(17), index=True)
    database: Mapped[str] = mapped_column(String(40), index=True)
    found: Mapped[bool] = mapped_column(default=False, index=True)
    release_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
