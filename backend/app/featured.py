"""Featured homepage picks + public site leads (Belarus reframe)."""

from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.listing_enrichment import build_listing_customs_map, get_listing_customs_summary, perform_listing_vin_check
from app.listing_import_age import IMPORT_AGE_RF_MONTHS, release_date_older_than_months
from app.manual_vin_check import (
    ManualVinCheckError,
    collect_adverts_for_url,
    normalize_avby_url,
    parse_avby_url,
    upsert_advert_listing,
)
from app.customs_vin import (
    CustomsVinError,
    is_explicit_not_found,
    lookup_customs_vin,
    normalize_vin,
    vin_is_valid,
)
from app.models import CarListing, FeaturedListing, ListingStatus, SiteLead

FEATURED_HOME_LIMIT = 10
FEATURED_POOL_LIMIT = 30

_VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$", re.IGNORECASE)
_URL_HINT_RE = re.compile(r"https?://|av\.by", re.IGNORECASE)


def listing_import_date_over_one_year(db: Session, listing: CarListing, *, today: date | None = None) -> bool:
    summary = get_listing_customs_summary(db, listing)
    if not summary or not summary.found or not summary.release_date:
        return False
    return release_date_older_than_months(summary.release_date, IMPORT_AGE_RF_MONTHS, today=today)


def assert_listing_eligible_for_featured(db: Session, listing: CarListing) -> None:
    if listing.status != ListingStatus.published:
        raise ValueError("В подборку можно добавить только опубликованное объявление")
    if not listing_import_date_over_one_year(db, listing):
        raise ValueError("Нужна проверенная дата ввоза старше 1 года")


def list_featured_rows(db: Session, *, active_only: bool = False) -> list[FeaturedListing]:
    query = db.query(FeaturedListing).order_by(
        FeaturedListing.sort_weight.desc(),
        FeaturedListing.id.asc(),
    )
    if active_only:
        query = query.filter(FeaturedListing.is_active.is_(True))
    return query.all()


def active_featured_listings(db: Session, *, today: date | None = None) -> list[CarListing]:
    """Active featured listings that still pass the >1 year import-date rule."""
    rows = list_featured_rows(db, active_only=True)
    if not rows:
        return []
    listing_ids = [row.listing_id for row in rows]
    listings = (
        db.query(CarListing)
        .filter(
            CarListing.id.in_(listing_ids),
            CarListing.status == ListingStatus.published,
        )
        .all()
    )
    by_id = {item.id: item for item in listings}
    customs_map = build_listing_customs_map(db, listings)
    eligible: list[CarListing] = []
    for row in rows:
        listing = by_id.get(row.listing_id)
        if listing is None:
            continue
        customs = customs_map.get(listing.id)
        if not customs or not customs.found or not customs.release_date:
            continue
        if not release_date_older_than_months(customs.release_date, IMPORT_AGE_RF_MONTHS, today=today):
            continue
        eligible.append(listing)
    return eligible


def rotate_featured_for_home(
    listings: list[CarListing],
    *,
    limit: int = FEATURED_HOME_LIMIT,
    today: date | None = None,
) -> list[CarListing]:
    """Deterministic daily shuffle, then take up to `limit`."""
    if not listings:
        return []
    day = today or date.today()
    seed_src = f"featured:{day.isoformat()}"
    seed = int(hashlib.sha256(seed_src.encode("utf-8")).hexdigest()[:16], 16)
    ordered = list(listings)
    rng = random.Random(seed)
    rng.shuffle(ordered)
    return ordered[:limit]


def home_featured_listings(db: Session, *, today: date | None = None) -> list[CarListing]:
    return rotate_featured_for_home(active_featured_listings(db, today=today), today=today)


def add_featured_listing(db: Session, listing_id: int, *, sort_weight: int = 0) -> FeaturedListing:
    listing = db.get(CarListing, listing_id)
    if listing is None:
        raise ValueError("Объявление не найдено")
    assert_listing_eligible_for_featured(db, listing)
    existing = db.query(FeaturedListing).filter(FeaturedListing.listing_id == listing_id).first()
    if existing:
        existing.is_active = True
        existing.sort_weight = sort_weight
        db.commit()
        db.refresh(existing)
        return existing
    active_count = db.query(FeaturedListing).filter(FeaturedListing.is_active.is_(True)).count()
    if active_count >= FEATURED_POOL_LIMIT:
        raise ValueError(f"В пуле уже {FEATURED_POOL_LIMIT} активных объявлений")
    row = FeaturedListing(listing_id=listing_id, sort_weight=sort_weight, is_active=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def set_featured_active(db: Session, featured_id: int, *, is_active: bool) -> FeaturedListing:
    row = db.get(FeaturedListing, featured_id)
    if row is None:
        raise ValueError("Запись подборки не найдена")
    if is_active:
        listing = db.get(CarListing, row.listing_id)
        if listing is None:
            raise ValueError("Объявление не найдено")
        assert_listing_eligible_for_featured(db, listing)
        active_count = (
            db.query(FeaturedListing)
            .filter(FeaturedListing.is_active.is_(True), FeaturedListing.id != featured_id)
            .count()
        )
        if active_count >= FEATURED_POOL_LIMIT:
            raise ValueError(f"В пуле уже {FEATURED_POOL_LIMIT} активных объявлений")
    row.is_active = is_active
    db.commit()
    db.refresh(row)
    return row


def remove_featured_listing(db: Session, featured_id: int) -> None:
    row = db.get(FeaturedListing, featured_id)
    if row is None:
        raise ValueError("Запись подборки не найдена")
    db.delete(row)
    db.commit()


def create_site_lead(
    db: Session,
    *,
    contact_name: str,
    contact: str,
    comment: str | None = None,
    listing_id: int | None = None,
    avby_url: str | None = None,
    source: str = "belarus_landing",
) -> SiteLead:
    name = (contact_name or "").strip()
    contact_value = (contact or "").strip()
    if not name:
        raise ValueError("Укажите имя")
    if not contact_value:
        raise ValueError("Укажите телефон или Telegram")
    lead = SiteLead(
        source=source[:40],
        contact_name=name[:120],
        contact=contact_value[:120],
        comment=(comment or "").strip()[:2000] or None,
        listing_id=listing_id,
        avby_url=(avby_url or "").strip()[:500] or None,
        is_read=False,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def list_site_leads(db: Session, *, limit: int = 100, offset: int = 0) -> list[SiteLead]:
    return (
        db.query(SiteLead)
        .order_by(desc(SiteLead.created_at), desc(SiteLead.id))
        .offset(offset)
        .limit(limit)
        .all()
    )


def mark_site_lead_read(db: Session, lead_id: int, *, is_read: bool = True) -> SiteLead:
    lead = db.get(SiteLead, lead_id)
    if lead is None:
        raise ValueError("Заявка не найдена")
    lead.is_read = is_read
    db.commit()
    db.refresh(lead)
    return lead


@dataclass
class ImportDateLookupResult:
    ok: bool
    input_kind: str  # vin | avby_url
    vin: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    # found | not_found | unavailable — distinguishes GTK miss vs GTK downtime
    customs_status: str | None = None
    message: str | None = None
    listing_id: int | None = None
    avby_url: str | None = None
    query: str | None = None


def _looks_like_vin(raw: str) -> bool:
    cleaned = re.sub(r"[\s\-]", "", raw or "").upper()
    return bool(_VIN_RE.match(cleaned))


def _resolve_vin_from_avby_url(db: Session, raw_url: str) -> tuple[str | None, CarListing | None, str | None]:
    """Return (vin, listing, error_message)."""
    try:
        parsed = parse_avby_url(raw_url)
        normalized = normalize_avby_url(raw_url)
    except ManualVinCheckError as exc:
        return None, None, str(exc)

    if parsed.kind != "listing" or not parsed.listing_id:
        return None, None, "Нужна ссылка на конкретное объявление av.by"

    listing = db.query(CarListing).filter(CarListing.avby_id == parsed.listing_id).first()
    if listing and listing.vin and vin_is_valid(normalize_vin(listing.vin)):
        return normalize_vin(listing.vin), listing, None

    try:
        _, adverts = collect_adverts_for_url(raw_url)
    except ManualVinCheckError as exc:
        if listing and listing.vin:
            return normalize_vin(listing.vin), listing, None
        return None, listing, str(exc)

    if not adverts:
        return None, listing, "Объявление на av.by не найдено"

    advert = adverts[0]
    listing, _created = upsert_advert_listing(db, advert)
    db.commit()
    db.refresh(listing)

    if listing.vin and vin_is_valid(normalize_vin(listing.vin)):
        return normalize_vin(listing.vin), listing, None

    try:
        check = perform_listing_vin_check(db, listing, allow_inactive=True)
    except Exception as exc:  # noqa: BLE001 — surface as user message
        return None, listing, f"Не удалось получить VIN: {exc}"

    if check.vin and vin_is_valid(normalize_vin(check.vin)):
        return normalize_vin(check.vin), listing, None
    return None, listing, check.vin_error or "VIN для этого объявления не найден"


def lookup_public_import_date(db: Session, raw_input: str) -> ImportDateLookupResult:
    text = (raw_input or "").strip()
    if not text:
        return ImportDateLookupResult(
            ok=False, input_kind="vin", message="Введите VIN или ссылку av.by", query=text
        )

    if _looks_like_vin(text) and not _URL_HINT_RE.search(text):
        vin = normalize_vin(text)
        if not vin_is_valid(vin):
            return ImportDateLookupResult(
                ok=False,
                input_kind="vin",
                query=text,
                message="Некорректный VIN. Используйте 17 символов без I, O, Q.",
            )
        try:
            result = lookup_customs_vin(db, vin)
        except CustomsVinError:
            return ImportDateLookupResult(
                ok=True,
                input_kind="vin",
                vin=vin,
                query=text,
                customs_found=None,
                customs_status="unavailable",
                message="Сайт таможни временно не отвечает",
            )
        if not result.found:
            if is_explicit_not_found(result):
                return ImportDateLookupResult(
                    ok=True,
                    input_kind="vin",
                    vin=vin,
                    query=text,
                    customs_found=False,
                    customs_status="not_found",
                    release_date=None,
                    message="В базе ГТК (физлица) запись не найдена",
                )
            return ImportDateLookupResult(
                ok=True,
                input_kind="vin",
                vin=vin,
                query=text,
                customs_found=None,
                customs_status="unavailable",
                message="Сайт таможни временно не отвечает",
            )
        return ImportDateLookupResult(
            ok=True,
            input_kind="vin",
            vin=vin,
            query=text,
            customs_found=True,
            customs_status="found",
            release_date=result.release_date,
            message=None if result.release_date else "Найдено в ГТК, дата ввоза не распознана",
        )

    # Treat as av.by URL
    try:
        normalized = normalize_avby_url(text)
    except ManualVinCheckError as exc:
        return ImportDateLookupResult(
            ok=False, input_kind="avby_url", query=text, message=str(exc)
        )

    vin, listing, err = _resolve_vin_from_avby_url(db, text)
    if not vin:
        return ImportDateLookupResult(
            ok=False,
            input_kind="avby_url",
            query=text,
            avby_url=normalized,
            listing_id=listing.id if listing else None,
            message=err or "Не удалось получить VIN по ссылке",
        )

    try:
        result = lookup_customs_vin(db, vin)
    except CustomsVinError:
        return ImportDateLookupResult(
            ok=True,
            input_kind="avby_url",
            vin=vin,
            query=text,
            avby_url=normalized,
            listing_id=listing.id if listing else None,
            customs_found=None,
            customs_status="unavailable",
            message="Сайт таможни временно не отвечает",
        )

    if not result.found:
        if is_explicit_not_found(result):
            return ImportDateLookupResult(
                ok=True,
                input_kind="avby_url",
                vin=vin,
                query=text,
                avby_url=normalized,
                listing_id=listing.id if listing else None,
                customs_found=False,
                customs_status="not_found",
                message="В базе ГТК (физлица) запись не найдена",
            )
        return ImportDateLookupResult(
            ok=True,
            input_kind="avby_url",
            vin=vin,
            query=text,
            avby_url=normalized,
            listing_id=listing.id if listing else None,
            customs_found=None,
            customs_status="unavailable",
            message="Сайт таможни временно не отвечает",
        )

    return ImportDateLookupResult(
        ok=True,
        input_kind="avby_url",
        vin=vin,
        query=text,
        avby_url=normalized,
        listing_id=listing.id if listing else None,
        customs_found=True,
        customs_status="found",
        release_date=result.release_date,
        message=None if result.release_date else "Найдено в ГТК, дата ввоза не распознана",
    )


@dataclass
class PublicInspectionCheckResult:
    ok: bool
    input_kind: str
    vin: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    customs_status: str | None = None
    message: str | None = None
    listing_id: int | None = None
    avby_url: str | None = None
    query: str | None = None
    power_hp: float | None = None
    engine_capacity_l: float | None = None
    engine_cc: int | None = None
    engine_cc_approximate: bool | None = None
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    verdict: dict | None = None


def run_public_inspection_check(
    db: Session,
    raw_input: str,
    *,
    reveal_vin: bool = False,
) -> PublicInspectionCheckResult:
    """Unified Проверка: VIN or av.by URL → customs date + RF util verdict."""
    from app.avby_engine_cc import resolve_engine_cc_for_listing
    from app.rf_util_eligibility import evaluate_rf_util_eligibility

    base = lookup_public_import_date(db, raw_input)
    power_hp: float | None = None
    engine_capacity_l: float | None = None
    engine_cc: int | None = None
    engine_cc_approximate: bool | None = None
    brand = model = None
    year = None
    listing = None
    if base.listing_id:
        listing = db.get(CarListing, base.listing_id)
        if listing is not None:
            if listing.engine_power_hp is not None:
                try:
                    power_hp = float(listing.engine_power_hp)
                except (TypeError, ValueError):
                    power_hp = None
            if listing.engine_capacity_l is not None:
                try:
                    engine_capacity_l = float(listing.engine_capacity_l)
                except (TypeError, ValueError):
                    engine_capacity_l = None
            brand = listing.brand
            model = listing.model
            year = listing.year

    if base.input_kind == "avby_url":
        resolved = resolve_engine_cc_for_listing(
            db,
            listing,
            engine_capacity_l=engine_capacity_l,
        )
        engine_cc = resolved.engine_cc
        engine_cc_approximate = bool(resolved.approximate) if engine_cc is not None else None

    verdict = None
    if base.ok:
        verdict = evaluate_rf_util_eligibility(
            release_date=base.release_date,
            power_hp=power_hp if base.input_kind == "avby_url" else None,
            engine_cc=engine_cc if base.input_kind == "avby_url" else None,
            engine_capacity_l=None if engine_cc is not None else (
                engine_capacity_l if base.input_kind == "avby_url" else None
            ),
            input_kind=base.input_kind,
            customs_found=base.customs_found,
            customs_status=base.customs_status,
        ).to_dict()

    # Hide VIN for URL checks unless admin; VIN typed by the user is always returned.
    vin_out = base.vin
    if base.input_kind == "avby_url" and not reveal_vin:
        vin_out = None

    return PublicInspectionCheckResult(
        ok=base.ok,
        input_kind=base.input_kind,
        vin=vin_out,
        release_date=base.release_date,
        customs_found=base.customs_found,
        customs_status=base.customs_status,
        message=base.message,
        listing_id=base.listing_id,
        avby_url=base.avby_url,
        query=base.query or raw_input.strip() or None,
        power_hp=power_hp if base.input_kind == "avby_url" else None,
        engine_capacity_l=engine_capacity_l if base.input_kind == "avby_url" else None,
        engine_cc=engine_cc if base.input_kind == "avby_url" else None,
        engine_cc_approximate=engine_cc_approximate if base.input_kind == "avby_url" else None,
        brand=brand if base.input_kind == "avby_url" else None,
        model=model if base.input_kind == "avby_url" else None,
        year=year if base.input_kind == "avby_url" else None,
        verdict=verdict,
    )
