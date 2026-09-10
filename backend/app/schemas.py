from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import ListingStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.seller


class LoginRequest(BaseModel):
    login: str = Field(min_length=3, max_length=80)
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: int
    username: str
    email: EmailStr
    name: str
    role: UserRole

    class Config:
        from_attributes = True


class ListingCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    brand: str
    model: str
    year: int = Field(ge=1950, le=2100)
    mileage: int = Field(ge=0)
    price: Decimal = Field(gt=0)
    city: str
    generation: str | None = None
    body_type: str | None = None
    drive_type: str | None = None
    transmission_type: str | None = None
    engine_type: str | None = None
    engine_capacity_l: Decimal | None = None
    engine_power_hp: int | None = Field(default=None, ge=1)
    vin_indicated: bool | None = None
    seller_name: str | None = None
    source_url: str | None = None
    cover_photo_url: str | None = None
    raw_photos: list[dict] | None = None
    description: str = Field(min_length=10)
    status: ListingStatus = ListingStatus.draft


class ListingUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    brand: str | None = None
    model: str | None = None
    year: int | None = Field(default=None, ge=1950, le=2100)
    mileage: int | None = Field(default=None, ge=0)
    price: Decimal | None = Field(default=None, gt=0)
    city: str | None = None
    generation: str | None = None
    body_type: str | None = None
    drive_type: str | None = None
    transmission_type: str | None = None
    engine_type: str | None = None
    engine_capacity_l: Decimal | None = None
    engine_power_hp: int | None = Field(default=None, ge=1)
    vin_indicated: bool | None = None
    seller_name: str | None = None
    source_url: str | None = None
    cover_photo_url: str | None = None
    raw_photos: list[dict] | None = None
    description: str | None = Field(default=None, min_length=10)
    status: ListingStatus | None = None


class ListingOut(BaseModel):
    id: int
    seller_id: int
    title: str
    brand: str
    model: str
    generation: str | None = None
    year: int
    mileage: int
    price: Decimal
    city: str
    body_type: str | None = None
    drive_type: str | None = None
    transmission_type: str | None = None
    engine_type: str | None = None
    engine_capacity_l: Decimal | None = None
    engine_power_hp: int | None = None
    vin_indicated: bool | None = None
    seller_name: str | None = None
    source_url: str | None = None
    cover_photo_url: str | None = None
    raw_photos: list[dict] | None = None
    description: str
    status: ListingStatus
    created_at: datetime

    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class PhotoPresignRequest(BaseModel):
    filename: str
    content_type: str


class PhotoPresignResponse(BaseModel):
    upload_url: str
    storage_key: str


class PhotoConfirmRequest(BaseModel):
    storage_key: str
    content_type: str
    sort_order: int = 0
    is_cover: bool = False


class CatalogPhotoOut(BaseModel):
    id: int
    catalog_item_id: int
    storage_key: str
    content_type: str
    sort_order: int
    is_cover: bool
    created_at: datetime
    file_url: str | None = None

    class Config:
        from_attributes = True


class AvbyServiceAccountPublic(BaseModel):
    id: int
    email: str | None = None
    phone: str | None = None
    phone_display: str | None = None
    login: str
    name: str
    status: str
    purpose: str = "parser"
    daily_vin_limit: int | None = None
    vin_checks_today: int = 0
    vin_checks_remaining: int | None = None
    is_active: bool
    api_key_masked: str | None = None
    has_auth_token: bool = False
    has_refresh_token: bool = False
    error_message: str | None = None
    notes: str | None = None
    registered_at: datetime | None = None
    created_at: datetime
    login_error: str | None = None


class AvbyServiceAccountSecrets(AvbyServiceAccountPublic):
    mailtm_password: str | None = None
    avby_password: str | None = None
    api_key: str | None = None
    auth_token: str | None = None
    refresh_token: str | None = None
    email_token: str | None = None


class AvbyServiceAccountCreateRequest(BaseModel):
    email: str | None = None
    phone: str | None = None
    avby_password: str
    name: str | None = None
    api_key: str | None = None
    auth_token: str | None = None
    refresh_token: str | None = None
    phone_verified: bool = True
    purpose: str = "vin_test"
    daily_vin_limit: int = 30
    is_active: bool | None = None
    login_on_create: bool = True
    notes: str | None = None

    @model_validator(mode="after")
    def require_email_or_phone(self) -> "AvbyServiceAccountCreateRequest":
        email = (self.email or "").strip()
        phone = (self.phone or "").strip()
        if not email and not phone:
            raise ValueError("Укажите email или номер телефона")
        if email and "@" not in email:
            raise ValueError("Некорректный email")
        return self


class AvbyServiceAccountUpdateRequest(BaseModel):
    is_active: bool | None = None
    notes: str | None = None
    daily_vin_limit: int | None = None
    email: str | None = None
    avby_password: str | None = None


class AvbyAccountsImportResult(BaseModel):
    imported: int
    skipped: int
    path: str


class ListingVinResponse(BaseModel):
    listing_id: int
    vin: str
    source: str
    cached: bool
    checks_remaining: int | None = None
    fetched_at: datetime | None = None


class ListingVinCheckResponse(BaseModel):
    listing_id: int
    vin: str | None = None
    vin_error: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    customs_error: str | None = None


class AppLogTailResponse(BaseModel):
    service: str
    lines: int
    content: str
    path: str | None = None
    log_dir: str
    fetched_at: str


class AnalyticsTopPage(BaseModel):
    path: str
    views: int


class AnalyticsTopUser(BaseModel):
    name: str
    events: int


class SiteEventOut(BaseModel):
    id: int
    event_type: str
    method: str
    path: str
    query_string: str | None = None
    status_code: int | None = None
    user_id: int | None = None
    user_email: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    referrer: str | None = None
    details: dict | None = None
    actor_label: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CatalogGenerationRatingUpdate(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str = ""
    rating: float | None = None

    @model_validator(mode="after")
    def validate_rating(self):
        if self.rating is None:
            return self
        if self.rating <= 0 or self.rating > 99:
            raise ValueError("Рейтинг должен быть числом от 1 до 99")
        return self


class CatalogGenerationRatingResult(BaseModel):
    make: str
    model: str
    generation: str
    rating: float | None
    updated_items: int
    mixed: bool = False


class CatalogGenerationVisibilityUpdate(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str = ""
    hidden: bool


class CatalogGenerationVisibilityResult(BaseModel):
    make: str
    model: str
    generation: str
    hidden: bool
    updated_items: int
    archived_listings: int = 0


class CatalogGenerationYearsUpdate(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str = ""
    year_from: int | None = Field(default=None, ge=1950, le=2100)
    year_to: int | None = Field(default=None, ge=1950, le=2100)

    @model_validator(mode="after")
    def validate_years(self):
        if self.year_from is not None and self.year_to is not None and self.year_from > self.year_to:
            raise ValueError("Год начала не может быть позже года окончания")
        return self


class CatalogGenerationYearsResult(BaseModel):
    make: str
    model: str
    generation: str
    year_from: int | None
    year_to: int | None
    production_years: str
    updated_items: int


class AnalyticsSummaryResponse(BaseModel):
    days: int
    views_today: int
    views_period: int
    sessions_today: int
    sessions_period: int
    actions_period: int
    top_pages: list[AnalyticsTopPage]
    top_users: list[AnalyticsTopUser]
    recent_events: list[SiteEventOut]
    event_labels: dict[str, str]
    fetched_at: str


class CatalogMatchCandidateIn(BaseModel):
    """Modification-level candidate from eu2 (same grain as catalog_items)."""

    external_ref: str | None = Field(default=None, max_length=120)
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1950, le=2100)
    body_type: str | None = Field(default=None, max_length=60)
    fuel_type: str | None = Field(default=None, max_length=30)
    engine_power_hp: int | None = Field(default=None, ge=1, le=2000)
    engine_volume_l: float | None = Field(default=None, ge=0.1, le=20)
    drivetrain: str | None = Field(default=None, max_length=30)
    transmission: str | None = Field(default=None, max_length=30)
    source_external_id: str | None = Field(default=None, max_length=120)


class CatalogMatchRequest(BaseModel):
    candidates: list[CatalogMatchCandidateIn] = Field(min_length=1, max_length=500)
    enqueue_gaps: bool = True
    source: str = Field(default="eu2", max_length=40)


class CatalogMatchResultOut(BaseModel):
    external_ref: str | None = None
    matched_catalog_item_id: int | None = None
    match_confidence: int = 0
    reason: str
    make: str
    model: str
    gap_id: int | None = None


class CatalogMatchResponse(BaseModel):
    results: list[CatalogMatchResultOut]
    matched: int
    not_found: int
    gaps_enqueued: int = 0


class CatalogItemPublic(BaseModel):
    id: int
    make: str
    model: str
    generation: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    engine_power_hp: int | None = None
    engine_volume_l: float | None = None
    drivetrain: str | None = None
    transmission: str | None = None
    source_site: str | None = None
    source_external_id: str | None = None
    source_url: str | None = None
    rating: float | None = None
    has_7_seats: bool = False
    hidden_from_catalog: bool = False


class CatalogGapIn(BaseModel):
    external_ref: str | None = Field(default=None, max_length=120)
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str | None = Field(default=None, max_length=120)
    year: int | None = Field(default=None, ge=1950, le=2100)
    body_type: str | None = Field(default=None, max_length=60)
    fuel_type: str | None = Field(default=None, max_length=30)
    engine_power_hp: int | None = Field(default=None, ge=1, le=2000)
    engine_volume_l: float | None = Field(default=None, ge=0.1, le=20)
    drivetrain: str | None = Field(default=None, max_length=30)
    transmission: str | None = Field(default=None, max_length=30)
    source_external_id: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=500)


class CatalogGapBatchRequest(BaseModel):
    gaps: list[CatalogGapIn] = Field(min_length=1, max_length=500)
    source: str = Field(default="eu2", max_length=40)


class CatalogGapOut(BaseModel):
    id: int
    source: str
    external_ref: str | None = None
    make: str
    model: str
    generation: str | None = None
    year: int | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    engine_power_hp: int | None = None
    engine_volume_l: float | None = None
    drivetrain: str | None = None
    transmission: str | None = None
    source_external_id: str | None = None
    status: str
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    resolved_catalog_item_id: int | None = None

    class Config:
        from_attributes = True


class CatalogGapBatchResponse(BaseModel):
    created: int
    gaps: list[CatalogGapOut]
