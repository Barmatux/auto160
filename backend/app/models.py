import enum
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - local sqlite without pgvector
    Vector = None  # type: ignore[misc, assignment]


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
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    email_verify_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email_verify_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listings: Mapped[list["CarListing"]] = relationship(back_populates="seller")

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None


class CarListing(Base):
    __tablename__ = "car_listings"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_car_listings_source_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    avby_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True, unique=True)
    brand: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    generation: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    mileage: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, index=True)
    price_byn_missing: Mapped[bool] = mapped_column(default=False, index=True)
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
    # Set when admin launches «Ручная проверка» for this listing (history feed).
    manual_vin_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    seller_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_photos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ListingStatus] = mapped_column(Enum(ListingStatus), default=ListingStatus.draft, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # av.by feed timestamps (renewedAt drives "новые объявления" sort on cars.av.by).
    avby_published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    avby_renewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    # Multi-source identity: "av.by" | "autoplius" | "auto24" | "mobile_de" (+ external_id).
    source: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    seller: Mapped[User] = relationship(back_populates="listings")
    catalog_item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_items.id"), nullable=True, index=True)
    catalog_item: Mapped["CatalogItem | None"] = relationship(foreign_keys=[catalog_item_id])
    embedding: Mapped["ListingEmbedding | None"] = relationship(
        back_populates="listing",
        uselist=False,
        cascade="all, delete-orphan",
    )


class ListingEmbedding(Base):
    """OpenAI-compatible embedding for a published car listing (pgvector)."""

    __tablename__ = "listing_embeddings"

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("car_listings.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # 1536 dims = text-embedding-3-small
    embedding: Mapped[list] = mapped_column(Vector(1536) if Vector is not None else JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    listing: Mapped["CarListing"] = relationship(back_populates="embedding")


class RagChunk(Base):
    """Embedded guide/FAQ chunk for chat RAG."""

    __tablename__ = "rag_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list] = mapped_column(Vector(1536) if Vector is not None else JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(80), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChatLog(Base):
    """Public chat dialog log (no secrets)."""

    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


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
    hidden_from_catalog: Mapped[bool] = mapped_column(default=False, index=True)
    has_7_seats: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    photos: Mapped[list["CatalogItemPhoto"]] = relationship(back_populates="catalog_item", cascade="all, delete-orphan")


class ListingAvgPrice(Base):
    """Market average BYN price by brand/model/year over a rolling window (not shown in UI yet)."""

    __tablename__ = "listing_avg_prices"
    __table_args__ = (
        UniqueConstraint(
            "brand",
            "model",
            "year",
            "window_days",
            name="uq_listing_avg_prices_brand_model_year_window",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    brand: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    avg_price_byn: Mapped[float] = mapped_column(Numeric(12, 2))
    min_price_byn: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_price_byn: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    sample_count_raw: Mapped[int] = mapped_column(Integer, default=0)
    outliers_removed: Mapped[int] = mapped_column(Integer, default=0)
    window_days: Mapped[int] = mapped_column(Integer, default=120, index=True)
    window_start: Mapped[datetime] = mapped_column(DateTime)
    window_end: Mapped[datetime] = mapped_column(DateTime)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


class ManualVinCheckLaunch(Base):
    """Which registered user launched «Ручная проверка» for a listing."""

    __tablename__ = "manual_vin_check_launches"
    __table_args__ = (
        UniqueConstraint("listing_id", "user_id", name="uq_manual_vin_check_launches_listing_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("car_listings.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    launched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    listing: Mapped["CarListing"] = relationship()
    user: Mapped["User"] = relationship()


class AvbySyncRunVinCheck(Base):
    __tablename__ = "avby_sync_run_vin_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sync_run_id: Mapped[int] = mapped_column(ForeignKey("avby_sync_runs.id", ondelete="CASCADE"), index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("car_listings.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(20), index=True)
    vin_obtained: Mapped[bool] = mapped_column(default=False)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    vin_indicated: Mapped[bool | None] = mapped_column(nullable=True)
    customs_checked: Mapped[bool] = mapped_column(default=False)
    customs_found: Mapped[bool | None] = mapped_column(nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AvbyVinFetch(Base):
    """Successful VIN reveal attributed to a service account (for daily admin stats)."""

    __tablename__ = "avby_vin_fetches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("avby_service_accounts.id", ondelete="CASCADE"),
        index=True,
    )
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("car_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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


class CatalogGap(Base):
    """Queue of catalog holes reported by internal consumers (eu2.by match not_found)."""

    __tablename__ = "catalog_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(40), default="eu2", index=True)
    external_ref: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    make: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    generation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    fuel_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    engine_power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_volume_l: Mapped[float | None] = mapped_column(Numeric(4, 1), nullable=True)
    drivetrain: Mapped[str | None] = mapped_column(String(30), nullable=True)
    transmission: Mapped[str | None] = mapped_column(String(30), nullable=True)
    source_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_catalog_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )


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


class MessageThreadStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class MessageSender(str, enum.Enum):
    visitor = "visitor"
    manager = "manager"


class MessageThread(Base):
    """Visitor↔manager conversation about a listing."""

    __tablename__ = "message_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("car_listings.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    contact_name: Mapped[str] = mapped_column(String(120))
    contact_phone: Mapped[str] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MessageThreadStatus] = mapped_column(
        Enum(MessageThreadStatus), default=MessageThreadStatus.open, nullable=False, index=True
    )
    visitor_last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    manager_last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    listing: Mapped["CarListing"] = relationship()
    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    thread_id: Mapped[int] = mapped_column(ForeignKey("message_threads.id", ondelete="CASCADE"), index=True)
    sender: Mapped[MessageSender] = mapped_column(Enum(MessageSender), nullable=False, index=True)
    sender_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    thread: Mapped["MessageThread"] = relationship(back_populates="messages")


class FeaturedListing(Base):
    """Admin-curated BY listing for the public homepage rotation."""

    __tablename__ = "featured_listings"
    __table_args__ = (UniqueConstraint("listing_id", name="uq_featured_listings_listing_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("car_listings.id", ondelete="CASCADE"), index=True)
    sort_weight: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    listing: Mapped["CarListing"] = relationship()


class SiteLead(Base):
    """Public contact lead from homepage modal or Belarus landing."""

    __tablename__ = "site_leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    contact_name: Mapped[str] = mapped_column(String(120))
    contact: Mapped[str] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("car_listings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    avby_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    listing: Mapped["CarListing | None"] = relationship()


class AvbyPriceStatTarget(Base):
    """Catalog generation (rating=1) mapped to av.by ocenka IDs."""

    __tablename__ = "avby_price_stat_targets"
    __table_args__ = (UniqueConstraint("catalog_slug", name="uq_avby_price_stat_targets_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    catalog_slug: Mapped[str] = mapped_column(String(200), index=True)
    make: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    generation: Mapped[str | None] = mapped_column(String(120), nullable=True)
    year_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    model_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    generation_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    resolve_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    resolve_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    year_stats: Mapped[list["AvbyPriceYearStat"]] = relationship(
        back_populates="target", cascade="all, delete-orphan"
    )


class AvbyPriceYearStat(Base):
    """Full av.by ocenka snapshot for one generation + year."""

    __tablename__ = "avby_price_year_stats"
    __table_args__ = (
        UniqueConstraint(
            "brand_id",
            "model_id",
            "generation_id",
            "year",
            name="uq_avby_price_year_stats_ids_year",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    target_id: Mapped[int] = mapped_column(
        ForeignKey("avby_price_stat_targets.id", ondelete="CASCADE"), index=True
    )
    brand_id: Mapped[int] = mapped_column(Integer, index=True)
    model_id: Mapped[int] = mapped_column(Integer, index=True)
    generation_id: Mapped[int] = mapped_column(Integer, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    make: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_byn: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    advert_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_advert_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_new_60d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_removed_60d: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    activity_by_month: Mapped[list | None] = mapped_column(JSON, nullable=True)
    main_filter_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    active_filter_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetch_status: Mapped[str] = mapped_column(String(20), default="ok", index=True)
    fetch_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    target: Mapped["AvbyPriceStatTarget"] = relationship(back_populates="year_stats")
    history_points: Mapped[list["AvbyPriceHistoryPoint"]] = relationship(
        back_populates="year_stat", cascade="all, delete-orphan"
    )
    sold_adverts: Mapped[list["AvbyPriceSoldAdvert"]] = relationship(
        back_populates="year_stat", cascade="all, delete-orphan"
    )


class AvbyPriceHistoryPoint(Base):
    __tablename__ = "avby_price_history_points"
    __table_args__ = (
        UniqueConstraint(
            "year_stat_id",
            "year",
            "month",
            name="uq_avby_price_history_points_stat_ym",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year_stat_id: Mapped[int] = mapped_column(
        ForeignKey("avby_price_year_stats.id", ondelete="CASCADE"), index=True
    )
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int] = mapped_column(Integer)
    median_price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)

    year_stat: Mapped["AvbyPriceYearStat"] = relationship(back_populates="history_points")


class AvbyPriceSoldAdvert(Base):
    __tablename__ = "avby_price_sold_adverts"
    __table_args__ = (
        UniqueConstraint(
            "year_stat_id",
            "avby_id",
            name="uq_avby_price_sold_adverts_stat_avby",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year_stat_id: Mapped[int] = mapped_column(
        ForeignKey("avby_price_year_stats.id", ondelete="CASCADE"), index=True
    )
    avby_id: Mapped[int] = mapped_column(Integer, index=True)
    price_usd: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    price_byn: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    days_on_sale: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    public_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    year_stat: Mapped["AvbyPriceYearStat"] = relationship(back_populates="sold_adverts")
