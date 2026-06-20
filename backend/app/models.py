import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    photos: Mapped[list["CatalogItemPhoto"]] = relationship(back_populates="catalog_item", cascade="all, delete-orphan")


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
