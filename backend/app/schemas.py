from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models import ListingStatus, UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    password_confirm: str = Field(min_length=6, max_length=128)
    role: UserRole = UserRole.seller

    @model_validator(mode="after")
    def passwords_must_match(self) -> "RegisterRequest":
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self


class LoginRequest(BaseModel):
    # Username or email (emails can be longer than usernames).
    login: str = Field(min_length=3, max_length=254)
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
    email_verified: bool = False

    class Config:
        from_attributes = True


class RegisterResponse(UserPublic):
    email_sent: bool = False
    message: str = ""


class ResendVerificationRequest(BaseModel):
    email: EmailStr


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
    daily_vin_limit: int | None = None
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


class ListingManualVinRequest(BaseModel):
    vin: str


class ManualVinCheckRunRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class ManualVinCheckRunItem(BaseModel):
    listing_id: int
    avby_id: int | None = None
    created: bool = False


class ManualVinCheckRunResponse(BaseModel):
    kind: str
    url: str
    advert_count: int
    listing_ids: list[int]
    items: list[ManualVinCheckRunItem]
    error: str | None = None


class ListingCustomsRecheckResponse(BaseModel):
    listing_id: int
    release_date: str | None = None
    customs_found: bool
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


class CatalogGenerationArbitrageTrackUpdate(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str = ""
    enabled: bool


class CatalogGenerationArbitrageTrackResult(BaseModel):
    make: str
    model: str
    generation: str
    enabled: bool
    updated_items: int


class CatalogGenerationCustomsCalcUpdate(BaseModel):
    make: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    generation: str = ""
    enabled: bool


class CatalogGenerationCustomsCalcResult(BaseModel):
    make: str
    model: str
    generation: str
    enabled: bool
    updated_items: int


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
    engine_capacity_cc: int | None = None
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


class MarketAvgPriceOut(BaseModel):
    brand: str
    model: str
    year: int
    window_days: int
    avg_price_byn: Decimal
    min_price_byn: Decimal | None = None
    max_price_byn: Decimal | None = None
    avg_price_usd: Decimal | None = None
    min_price_usd: Decimal | None = None
    max_price_usd: Decimal | None = None
    sample_count: int
    sample_count_raw: int = 0
    outliers_removed: int = 0
    currency: str = "BYN"
    window_start: datetime
    window_end: datetime
    computed_at: datetime

    class Config:
        from_attributes = True


class MarketAvgPriceListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[MarketAvgPriceOut]
    # NBRB FX used for USD fields (null if rate fetch failed).
    usd_rate: float | None = None
    usd_scale: int | None = None
    usd_rate_date: datetime | None = None
    usd_rate_source: str | None = "НБ РБ"


class FeaturedListingOut(BaseModel):
    id: int
    listing_id: int
    sort_weight: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FeaturedListingCreateRequest(BaseModel):
    listing_id: int
    sort_weight: int = 0


class FeaturedListingActiveRequest(BaseModel):
    is_active: bool


class SiteLeadCreateRequest(BaseModel):
    contact_name: str
    contact: str
    comment: str | None = None
    listing_id: int | None = None
    avby_url: str | None = None
    source: str = "belarus_landing"


class SiteLeadOut(BaseModel):
    id: int
    source: str
    contact_name: str
    contact: str
    comment: str | None = None
    listing_id: int | None = None
    avby_url: str | None = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SiteLeadReadRequest(BaseModel):
    is_read: bool = True


class ImportDateLookupRequest(BaseModel):
    query: str


class ImportDateLookupResponse(BaseModel):
    ok: bool
    input_kind: str
    vin: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    message: str | None = None
    listing_id: int | None = None
    avby_url: str | None = None


class CustomsVehicleSpecOut(BaseModel):
    id: int
    make: str
    model: str
    generation: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    engine_cc: int
    power_hp: float
    engine_kind: str
    fuel_label: str | None = None
    notes: str | None = None
    is_active: bool
    sort_weight: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomsVehicleSpecCreateRequest(BaseModel):
    make: str
    model: str
    generation: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    engine_cc: int
    power_hp: float
    engine_kind: str = "ice"
    fuel_label: str | None = None
    notes: str | None = None
    is_active: bool = True
    sort_weight: int = 0


class CustomsVehicleSpecUpdateRequest(BaseModel):
    make: str | None = None
    model: str | None = None
    generation: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    engine_cc: int | None = None
    power_hp: float | None = None
    engine_kind: str | None = None
    fuel_label: str | None = None
    notes: str | None = None
    is_active: bool | None = None
    sort_weight: int | None = None


class CustomsDbMakeOut(BaseModel):
    id: int
    name: str
    sort_weight: int
    is_active: bool

    class Config:
        from_attributes = True


class CustomsDbMakeCreateRequest(BaseModel):
    name: str
    sort_weight: int = 0


class CustomsDbModelOut(BaseModel):
    id: int
    make_id: int
    name: str
    sort_weight: int
    is_active: bool

    class Config:
        from_attributes = True


class CustomsDbModelCreateRequest(BaseModel):
    make_id: int
    name: str
    sort_weight: int = 0


class CustomsDbLiterOut(BaseModel):
    id: int
    model_id: int
    liters: float
    sort_weight: int
    is_active: bool

    class Config:
        from_attributes = True


class CustomsDbLiterCreateRequest(BaseModel):
    model_id: int
    liters: float
    sort_weight: int = 0


class CustomsDbCcOut(BaseModel):
    id: int
    liter_id: int
    engine_cc: int
    power_hp: float | None = None
    notes: str | None = None
    sort_weight: int
    is_active: bool

    class Config:
        from_attributes = True


class CustomsDbMotorOut(BaseModel):
    """Flattened engine configuration for calculator: model → motor → exact cc."""

    id: int
    liter_id: int
    liters: float
    engine_cc: int
    power_hp: float | None = None
    notes: str | None = None
    label: str


class CustomsCatalogModelOut(BaseModel):
    name: str


class CustomsCatalogMotorOut(BaseModel):
    id: int
    generation: str | None = None
    liters: float | None = None
    engine_cc: int
    power_hp: float
    engine_kind: str = "ice"
    label: str


class CustomsDbCcCreateRequest(BaseModel):
    liter_id: int
    engine_cc: int
    power_hp: float | None = None
    notes: str | None = None
    sort_weight: int = 0


class CustomsCalcRequest(BaseModel):
    age_band: str
    engine_cc: float = 0
    power_hp: float = 0
    price: float
    currency: str = "EUR"
    importer: str = "personal"
    engine_kind: str = "ice"
    vehicle_spec_id: int | None = None
    engine_cc_id: int | None = None
    catalog_item_id: int | None = None


class CustomsCalcResponse(BaseModel):
    ok: bool
    error: str | None = None
    age_years: float | None = None
    age_band: str | None = None
    age_band_label: str | None = None
    customs_value_rub: float | None = None
    duty_rub: float | None = None
    clearance_fee_rub: float | None = None
    util_sbor_rub: float | None = None
    util_coefficient: float | None = None
    util_preferential: bool = False
    total_rub: float | None = None
    eur_rub: float | None = None
    usd_rub: float | None = None
    byn_rub: float | None = None
    notes: list[str] = []
    breakdown: dict = {}
    vehicle_label: str | None = None
