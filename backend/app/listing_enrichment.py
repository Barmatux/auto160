"""Auto-fetch VIN and customs data for listings tied to catalog rating=1."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.avby_offer_metadata import fetch_and_apply_offer_vin_metadata
from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
from app.customs_vin import (
    DATABASE_PERSONAL,
    CustomsVinError,
    has_fresh_customs_check,
    lookup_customs_vin,
    normalize_vin,
    vin_is_valid,
)
from app.fuel_type_labels import FUEL_GROUP_DIESEL, classify_fuel_type
from app.models import CarListing, CatalogItem, ListingStatus, VinCustomsCheck
from app.transmission_labels import TRANSMISSION_SLUG_MANUAL, classify_transmission_slug
from app.sync_run_vin_log import PHASE_RATING1, record_sync_run_vin_check


def normalize_catalog_name(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip().lower().replace("ё", "е")
    normalized = re.sub(r"[^a-zа-я0-9]+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


@dataclass(frozen=True)
class RatingOneTarget:
    make_n: str
    model_n: str
    year_from: int | None
    year_to: int | None


@dataclass
class ListingEnrichmentStats:
    eligible: int = 0
    attempted: int = 0
    vin_fetched: int = 0
    vin_cached: int = 0
    customs_checked: int = 0
    customs_cached: int = 0
    skipped_already_enriched: int = 0
    skipped_limit: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VinCheckListingFilters:
    only_automatic: bool = False
    only_diesel: bool = False
    year_from_2020: bool = False
    mileage_to_100k: bool = False
    mileage_to_200k: bool = False
    brand: str | None = None
    model: str | None = None
    sort: str = "added"


VIN_CHECK_SORT_ADDED = "added"
VIN_CHECK_SORT_PRICE = "price"
VIN_CHECK_SORT_MILEAGE = "mileage"
VIN_CHECK_SORT_VALUES = frozenset(
    {
        VIN_CHECK_SORT_ADDED,
        VIN_CHECK_SORT_PRICE,
        VIN_CHECK_SORT_MILEAGE,
    }
)
VIN_CHECK_SORT_LABELS = {
    VIN_CHECK_SORT_ADDED: "По дате добавления",
    VIN_CHECK_SORT_PRICE: "По цене",
    VIN_CHECK_SORT_MILEAGE: "По пробегу",
}
VIN_CHECK_DEFAULT_YEAR_FROM = 2010
VIN_CHECK_EXCLUDED_SOURCES = frozenset({"autoplius", "auto24", "mobile_de"})


def listing_is_belarus_vin_check_source(listing: CarListing) -> bool:
    """VIN CHECK is Belarus customs — skip Lithuania/Estonia/Germany feeds."""
    source = (getattr(listing, "source", None) or "").strip().casefold()
    if not source:
        return True
    return source not in VIN_CHECK_EXCLUDED_SOURCES


def _belarus_vin_check_listings_query_filter():
    return or_(
        CarListing.source.is_(None),
        ~CarListing.source.in_(tuple(VIN_CHECK_EXCLUDED_SOURCES)),
    )


def normalize_vin_check_sort(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    if cleaned in VIN_CHECK_SORT_VALUES:
        return cleaned
    return VIN_CHECK_SORT_ADDED


def _listing_created_at_sort_value(listing: CarListing) -> float:
    created = getattr(listing, "created_at", None)
    if created is None:
        return 0.0
    try:
        return float(created.timestamp())
    except (AttributeError, OSError, TypeError, ValueError):
        return 0.0


def build_vin_check_brand_model_map(db: Session) -> dict[str, list[str]]:
    """Unique make → models for catalog items with rating 1 (av.by)."""
    rows = (
        db.query(CatalogItem.make, CatalogItem.model)
        .filter(
            CatalogItem.rating == 1,
            CatalogItem.source_site == "av.by",
            CatalogItem.make.isnot(None),
            CatalogItem.model.isnot(None),
        )
        .all()
    )
    mapping: dict[str, list[str]] = {}
    for make, model in rows:
        brand = (make or "").strip()
        model_name = (model or "").strip()
        if not brand or not model_name:
            continue
        models = mapping.setdefault(brand, [])
        if model_name not in models:
            models.append(model_name)
    for brand, models in mapping.items():
        mapping[brand] = sorted(models, key=lambda value: value.casefold())
    return dict(sorted(mapping.items(), key=lambda item: item[0].casefold()))


@dataclass(frozen=True)
class VinFoundDateFilter:
    date_from: date | None = None
    date_to: date | None = None

    @property
    def active(self) -> bool:
        return self.date_from is not None or self.date_to is not None

    def label(self) -> str | None:
        if self.date_from and self.date_to:
            if self.date_from == self.date_to:
                return self.date_from.strftime("%d.%m.%Y")
            return f"{self.date_from.strftime('%d.%m.%Y')} – {self.date_to.strftime('%d.%m.%Y')}"
        if self.date_from:
            return f"с {self.date_from.strftime('%d.%m.%Y')}"
        if self.date_to:
            return f"до {self.date_to.strftime('%d.%m.%Y')}"
        return None


VIN_FOUND_IMPORT_FILTER_ALL = "all"
VIN_FOUND_IMPORT_FILTER_GT10 = "gt10"
VIN_FOUND_IMPORT_FILTER_GT12 = "gt12"
VIN_FOUND_IMPORT_FILTER_UNSET = "unset"
VIN_FOUND_IMPORT_FILTER_VALUES = frozenset(
    {
        VIN_FOUND_IMPORT_FILTER_ALL,
        VIN_FOUND_IMPORT_FILTER_GT10,
        VIN_FOUND_IMPORT_FILTER_GT12,
        VIN_FOUND_IMPORT_FILTER_UNSET,
    }
)
VIN_FOUND_IMPORT_FILTER_LABELS = {
    VIN_FOUND_IMPORT_FILTER_ALL: "Все даты",
    VIN_FOUND_IMPORT_FILTER_GT10: ">10 месяцев",
    VIN_FOUND_IMPORT_FILTER_GT12: ">12 месяцев",
    VIN_FOUND_IMPORT_FILTER_UNSET: "Дата не установлена",
}


@dataclass(frozen=True)
class VinFoundImportFilter:
    value: str = VIN_FOUND_IMPORT_FILTER_ALL

    def normalized(self) -> "VinFoundImportFilter":
        value = self.value if self.value in VIN_FOUND_IMPORT_FILTER_VALUES else VIN_FOUND_IMPORT_FILTER_ALL
        return VinFoundImportFilter(value=value)

    @property
    def active(self) -> bool:
        return self.normalized().value != VIN_FOUND_IMPORT_FILTER_ALL

    def label(self) -> str | None:
        current = self.normalized()
        if current.value == VIN_FOUND_IMPORT_FILTER_ALL:
            return None
        return VIN_FOUND_IMPORT_FILTER_LABELS.get(current.value)


def months_before(today: date, months: int) -> date:
    """Return the calendar date `months` months before `today`."""
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def listing_matches_vin_found_import_filter(
    release_date: str | None,
    import_filter: VinFoundImportFilter | None = None,
    *,
    today: date | None = None,
) -> bool:
    current = (import_filter or VinFoundImportFilter()).normalized()
    if not current.active:
        return True

    from app.vin_analytics import parse_filter_date

    parsed = parse_filter_date(release_date)
    if current.value == VIN_FOUND_IMPORT_FILTER_UNSET:
        return parsed is None

    if parsed is None:
        return False

    ref = today or date.today()
    if current.value == VIN_FOUND_IMPORT_FILTER_GT10:
        return parsed < months_before(ref, 10)
    if current.value == VIN_FOUND_IMPORT_FILTER_GT12:
        return parsed < months_before(ref, 12)
    return True


def listing_vin_check_at(listing: CarListing) -> datetime | None:
    return getattr(listing, "vin_fetched_at", None) or getattr(listing, "created_at", None)


def listing_matches_vin_found_date_filter(
    listing: CarListing,
    date_filter: VinFoundDateFilter | None = None,
) -> bool:
    if date_filter is None or not date_filter.active:
        return True
    checked_at = listing_vin_check_at(listing)
    if checked_at is None:
        return False
    checked_day = checked_at.date() if isinstance(checked_at, datetime) else checked_at
    if date_filter.date_from and checked_day < date_filter.date_from:
        return False
    if date_filter.date_to and checked_day > date_filter.date_to:
        return False
    return True


@dataclass(frozen=True)
class ListingCustomsSummary:
    found: bool
    release_date: str | None
    checked_at: object | None
    cached: bool = False


def build_rating_one_targets(db: Session) -> list[RatingOneTarget]:
    rows = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.rating == 1,
            CatalogItem.source_site == "av.by",
        )
        .all()
    )
    targets: list[RatingOneTarget] = []
    seen: set[tuple[str, str, int | None, int | None]] = set()
    for item in rows:
        make_n = normalize_catalog_name(item.make)
        model_n = normalize_catalog_name(item.model)
        if not make_n or not model_n:
            continue
        key = (make_n, model_n, item.year_from, item.year_to)
        if key in seen:
            continue
        seen.add(key)
        targets.append(
            RatingOneTarget(
                make_n=make_n,
                model_n=model_n,
                year_from=item.year_from,
                year_to=item.year_to,
            )
        )
    return targets


def listing_matches_rating_one(listing: CarListing, targets: list[RatingOneTarget]) -> bool:
    if not targets or not listing.brand or not listing.model:
        return False
    make_n = normalize_catalog_name(listing.brand)
    model_n = normalize_catalog_name(listing.model)
    year = listing.year
    for target in targets:
        if target.make_n != make_n or target.model_n != model_n:
            continue
        if target.year_from is not None and year < target.year_from:
            continue
        if target.year_to is not None and year > target.year_to:
            continue
        return True
    return False


def listing_has_saved_vin(listing: CarListing) -> bool:
    return len((listing.vin or "").strip()) == 17


def listing_needs_enrichment(db: Session, listing: CarListing) -> bool:
    if not listing_has_saved_vin(listing):
        return True
    return not has_fresh_customs_check(db, listing.vin or "", database=DATABASE_PERSONAL)


def enrich_listing_vin_and_customs(
    db: Session,
    listing: CarListing,
    *,
    sync_run_id: int | None = None,
    allow_inactive: bool = False,
) -> ListingEnrichmentStats:
    stats = ListingEnrichmentStats(attempted=1)
    had_vin_before = listing_has_saved_vin(listing)
    error_message: str | None = None
    customs_checked = False
    customs_found: bool | None = None
    vin_obtained = False

    if not listing.avby_id:
        error_message = "no av.by id"
        stats.errors.append(f"listing {listing.id}: {error_message}")
        if sync_run_id is not None:
            record_sync_run_vin_check(
                db,
                sync_run_id=sync_run_id,
                listing=listing,
                phase=PHASE_RATING1,
                vin_obtained=False,
                error_message=error_message,
            )
            db.commit()
        return stats

    vin = (listing.vin or "").strip().upper()
    if listing_has_saved_vin(listing):
        stats.vin_cached += 1
    else:
        meta_result = fetch_and_apply_offer_vin_metadata(db, listing)
        if meta_result.error:
            error_message = f"metadata {meta_result.error}"
            stats.errors.append(f"listing {listing.id}: {error_message}")
        elif meta_result.vin_saved:
            stats.vin_fetched += 1
            vin_obtained = True

        if listing_has_saved_vin(listing):
            vin = (listing.vin or "").strip().upper()
        else:
            try:
                vin_result = get_or_fetch_listing_vin(db, listing, allow_inactive=allow_inactive)
            except AvbyVinError as exc:
                error_message = str(exc)
                stats.errors.append(f"listing {listing.id}: {error_message}")
                if sync_run_id is not None:
                    record_sync_run_vin_check(
                        db,
                        sync_run_id=sync_run_id,
                        listing=listing,
                        phase=PHASE_RATING1,
                        vin_obtained=False,
                        error_message=error_message,
                    )
                    db.commit()
                return stats

            vin = (vin_result.vin or "").strip().upper()
            if not vin:
                error_message = "empty VIN"
                stats.errors.append(f"listing {listing.id}: {error_message}")
                if sync_run_id is not None:
                    record_sync_run_vin_check(
                        db,
                        sync_run_id=sync_run_id,
                        listing=listing,
                        phase=PHASE_RATING1,
                        vin_obtained=False,
                        error_message=error_message,
                    )
                    db.commit()
                return stats

            if vin_result.cached:
                stats.vin_cached += 1
            else:
                stats.vin_fetched += 1
                vin_obtained = True

    if not vin_obtained and not had_vin_before and listing_has_saved_vin(listing):
        vin_obtained = True

    if has_fresh_customs_check(db, vin, database=DATABASE_PERSONAL):
        stats.customs_cached += 1
        summary = get_listing_customs_summary(db, listing)
        if summary is not None:
            customs_checked = True
            customs_found = summary.found
        if sync_run_id is not None:
            record_sync_run_vin_check(
                db,
                sync_run_id=sync_run_id,
                listing=listing,
                phase=PHASE_RATING1,
                vin_obtained=vin_obtained,
                vin=vin,
                vin_indicated=listing.vin_indicated,
                customs_checked=customs_checked,
                customs_found=customs_found,
                error_message=error_message,
            )
            db.commit()
        return stats

    try:
        customs_result = lookup_customs_vin(db, vin, database=DATABASE_PERSONAL)
    except CustomsVinError as exc:
        error_message = f"customs {exc}"
        stats.errors.append(f"listing {listing.id}: {error_message}")
        if sync_run_id is not None:
            record_sync_run_vin_check(
                db,
                sync_run_id=sync_run_id,
                listing=listing,
                phase=PHASE_RATING1,
                vin_obtained=vin_obtained,
                vin=vin,
                vin_indicated=listing.vin_indicated,
                error_message=error_message,
            )
            db.commit()
        return stats

    stats.customs_checked += 1
    customs_checked = True
    customs_found = customs_result.found
    if customs_result.cached:
        stats.customs_cached += 1

    if sync_run_id is not None:
        record_sync_run_vin_check(
            db,
            sync_run_id=sync_run_id,
            listing=listing,
            phase=PHASE_RATING1,
            vin_obtained=vin_obtained,
            vin=vin,
            vin_indicated=listing.vin_indicated,
            customs_checked=customs_checked,
            customs_found=customs_found,
            error_message=error_message,
        )
        db.commit()
    return stats


def enrich_rating_one_listings(
    db: Session,
    listings: list[CarListing],
    *,
    targets: list[RatingOneTarget] | None = None,
    limit: int | None = 20,
    sync_run_id: int | None = None,
) -> ListingEnrichmentStats:
    if not listings:
        return ListingEnrichmentStats()

    rating_targets = targets if targets is not None else build_rating_one_targets(db)
    total = ListingEnrichmentStats()
    processed = 0

    for listing in listings:
        if not listing_is_belarus_vin_check_source(listing):
            continue
        if not listing_matches_rating_one(listing, rating_targets):
            continue
        total.eligible += 1

        if not listing_needs_enrichment(db, listing):
            total.skipped_already_enriched += 1
            continue

        if limit is not None and processed >= limit:
            total.skipped_limit += 1
            continue

        item_stats = enrich_listing_vin_and_customs(db, listing, sync_run_id=sync_run_id)
        total.attempted += item_stats.attempted
        total.vin_fetched += item_stats.vin_fetched
        total.vin_cached += item_stats.vin_cached
        total.customs_checked += item_stats.customs_checked
        total.customs_cached += item_stats.customs_cached
        total.errors.extend(item_stats.errors)
        processed += 1

        if any("429" in err or "Daily VIN limit" in err for err in item_stats.errors):
            break

    return total


def get_listing_customs_summary(db: Session, listing: CarListing) -> ListingCustomsSummary | None:
    vin = (listing.vin or "").strip().upper()
    if len(vin) != 17:
        return None
    row = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin == vin,
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .first()
    )
    if row is None:
        return None
    return ListingCustomsSummary(
        found=row.found,
        release_date=row.release_date,
        checked_at=row.checked_at,
        cached=True,
    )


@dataclass(frozen=True)
class ListingVinCheckResult:
    vin: str | None = None
    vin_error: str | None = None
    release_date: str | None = None
    customs_found: bool | None = None
    customs_error: str | None = None


def _last_error_prefix(errors: list[str], prefix: str) -> str | None:
    for err in reversed(errors):
        if prefix in err:
            return err.split(":", 1)[-1].strip()
    return None


def perform_listing_vin_check(
    db: Session,
    listing: CarListing,
    *,
    allow_inactive: bool = True,
) -> ListingVinCheckResult:
    """Admin VIN CHECK: fetch VIN (+ customs). allow_inactive defaults True so
    inactive vin_test accounts out of parser rotation still work for manual checks.
    """
    stats = enrich_listing_vin_and_customs(db, listing, allow_inactive=allow_inactive)
    db.refresh(listing)

    if listing_has_saved_vin(listing):
        vin = (listing.vin or "").strip().upper()
        summary = get_listing_customs_summary(db, listing)
        if summary is not None:
            if summary.found and summary.release_date:
                return ListingVinCheckResult(
                    vin=vin,
                    release_date=summary.release_date,
                    customs_found=True,
                )
            if summary.found:
                return ListingVinCheckResult(
                    vin=vin,
                    customs_found=True,
                    customs_error="Найдено в ГТК, дата не распознана",
                )
            return ListingVinCheckResult(
                vin=vin,
                customs_found=False,
                customs_error="Не найдено в базе ГТК",
            )

        customs_error = _last_error_prefix(stats.errors, "customs ")
        if customs_error:
            return ListingVinCheckResult(vin=vin, customs_error=customs_error)
        if stats.customs_checked or stats.customs_cached:
            return ListingVinCheckResult(
                vin=vin,
                customs_error="Не удалось получить дату ввоза",
            )
        return ListingVinCheckResult(vin=vin, customs_error="Проверка таможни не выполнена")

    vin_error = _last_error_prefix(stats.errors, "listing ")
    if not vin_error:
        vin_error = _last_error_prefix(stats.errors, "metadata ")
    if not vin_error and stats.errors:
        vin_error = stats.errors[-1].split(":", 1)[-1].strip()
    if not vin_error:
        vin_error = "Не удалось получить VIN"
    return ListingVinCheckResult(vin_error=vin_error)


def apply_manual_listing_vin(db: Session, listing: CarListing, raw_vin: str) -> ListingVinCheckResult:
    """Persist an admin-entered VIN and refresh customs import date."""
    normalized = normalize_vin(raw_vin)
    if not vin_is_valid(normalized):
        return ListingVinCheckResult(
            vin_error="Некорректный VIN: нужны 17 символов без букв I, O, Q",
        )

    listing.vin = normalized
    listing.vin_fetched_at = datetime.now(UTC)
    if listing.vin_indicated is None:
        listing.vin_indicated = True
    db.add(listing)
    db.commit()
    db.refresh(listing)

    release_date, customs_error = recheck_listing_customs_import_date(db, listing)
    if release_date:
        return ListingVinCheckResult(
            vin=normalized,
            release_date=release_date,
            customs_found=True,
        )
    if customs_error == "Найдено в ГТК, дата не распознана":
        return ListingVinCheckResult(
            vin=normalized,
            customs_found=True,
            customs_error=customs_error,
        )
    if customs_error == "Не найдено в базе ГТК":
        return ListingVinCheckResult(
            vin=normalized,
            customs_found=False,
            customs_error=customs_error,
        )
    return ListingVinCheckResult(
        vin=normalized,
        customs_error=customs_error or "Не удалось получить дату ввоза",
    )


def format_vin_check_model_label(listing: CarListing) -> str:
    brand = (listing.brand or "").strip()
    model = (listing.model or "").strip()
    return f"{brand} {model}".strip()


def listing_vin_check_was_launched(listing: CarListing) -> bool:
    if not listing.avby_id:
        return False
    return listing.vin_fetched_at is not None or listing_has_saved_vin(listing)


@dataclass(frozen=True)
class VinCheckPageStats:
    checks_launched: int
    checks_success: int
    vin_by_model: tuple[tuple[str, int], ...]


def build_vin_check_page_stats(listings: list[CarListing]) -> VinCheckPageStats:
    launched = 0
    success = 0
    by_model: dict[str, int] = {}
    for listing in listings:
        if not listing.avby_id:
            continue
        if listing_vin_check_was_launched(listing):
            launched += 1
        if listing_has_saved_vin(listing):
            success += 1
            label = format_vin_check_model_label(listing)
            if label:
                by_model[label] = by_model.get(label, 0) + 1
    sorted_models = sorted(by_model.items(), key=lambda item: (-item[1], item[0].casefold()))
    return VinCheckPageStats(
        checks_launched=launched,
        checks_success=success,
        vin_by_model=tuple(sorted_models),
    )


def format_vin_check_stats_summary(stats: VinCheckPageStats) -> str:
    parts = [
        f"По {stats.checks_launched} vin запущена проверка.",
        f"Успешно {stats.checks_success}.",
    ]
    if stats.vin_by_model:
        model_bits = ", ".join(f"{label} - {count}" for label, count in stats.vin_by_model)
        parts.append(f"Собрано VIN по : {model_bits}")
    else:
        parts.append("Собрано VIN по : —")
    return " ".join(parts)


def _match_orphan_vin_fetch(
    listing: CarListing,
    orphan_fetches: list,
    *,
    max_delta_seconds: int = 120,
) -> int | None:
    if not listing.vin_fetched_at or not orphan_fetches:
        return None
    best_account_id: int | None = None
    best_delta: float | None = None
    listing_ts = listing.vin_fetched_at
    for fetch in orphan_fetches:
        if fetch.created_at is None:
            continue
        delta = abs((fetch.created_at - listing_ts).total_seconds())
        if delta > max_delta_seconds:
            continue
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_account_id = fetch.account_id
    return best_account_id


def build_listing_vin_account_labels(db: Session, listings: list[CarListing]) -> dict[int, str]:
    if not listings:
        return {}

    from app.avby_accounts import account_display_login
    from app.models import AvbyServiceAccount, AvbyVinFetch

    listing_ids = [listing.id for listing in listings]
    account_ids: dict[int, int] = {}

    fetches = (
        db.query(AvbyVinFetch)
        .filter(AvbyVinFetch.listing_id.in_(listing_ids))
        .order_by(AvbyVinFetch.created_at.desc())
        .all()
    )
    for fetch in fetches:
        if fetch.listing_id is None or fetch.listing_id in account_ids:
            continue
        account_ids[fetch.listing_id] = fetch.account_id

    missing_with_fetch_time = [
        listing for listing in listings if listing.id not in account_ids and listing.vin_fetched_at
    ]
    if missing_with_fetch_time:
        min_ts = min(listing.vin_fetched_at for listing in missing_with_fetch_time) - timedelta(seconds=120)
        max_ts = max(listing.vin_fetched_at for listing in missing_with_fetch_time) + timedelta(seconds=120)
        orphan_fetches = (
            db.query(AvbyVinFetch)
            .filter(
                AvbyVinFetch.listing_id.is_(None),
                AvbyVinFetch.created_at >= min_ts,
                AvbyVinFetch.created_at <= max_ts,
            )
            .order_by(AvbyVinFetch.created_at.desc())
            .all()
        )
        for listing in missing_with_fetch_time:
            matched_account_id = _match_orphan_vin_fetch(listing, orphan_fetches)
            if matched_account_id is not None:
                account_ids[listing.id] = matched_account_id

    labels: dict[int, str] = {}
    if account_ids:
        accounts = {
            row.id: row
            for row in db.query(AvbyServiceAccount)
            .filter(AvbyServiceAccount.id.in_(account_ids.values()))
            .all()
        }
        for listing_id, account_id in account_ids.items():
            account = accounts.get(account_id)
            if account is not None:
                labels[listing_id] = account_display_login(account)

    for listing in listings:
        if listing.id in labels:
            continue
        if listing_has_saved_vin(listing) and listing.vin_fetched_at is None:
            labels[listing.id] = "Из объявления"
    return labels


def recheck_listing_customs_import_date(db: Session, listing: CarListing) -> tuple[str | None, str | None]:
    if not listing_has_saved_vin(listing):
        return None, "Нет VIN"
    vin = (listing.vin or "").strip().upper()
    try:
        result = lookup_customs_vin(db, vin, database=DATABASE_PERSONAL, force_refresh=True)
    except CustomsVinError as exc:
        return None, str(exc)
    if result.found and result.release_date:
        return result.release_date, None
    if result.found:
        return None, "Найдено в ГТК, дата не распознана"
    return None, "Не найдено в базе ГТК"


def build_vin_found_rows(
    db: Session,
    listings: list[CarListing],
    *,
    resolve_cover_urls,
    build_customs_map,
) -> list[dict]:
    if not listings:
        return []
    cover_urls = resolve_cover_urls(listings, db)
    customs_map = build_customs_map(db, listings)
    account_labels = build_listing_vin_account_labels(db, listings)
    rows: list[dict] = []
    for listing in listings:
        customs = customs_map.get(listing.id)
        checked_at = listing_vin_check_at(listing)
        rows.append(
            {
                "listing": listing,
                "photo_url": cover_urls.get(listing.id),
                "import_date": customs.release_date if customs and customs.found and customs.release_date else None,
                "account_label": account_labels.get(listing.id),
                "checked_at": checked_at,
            }
        )
    return rows


def count_rating_one_listings_with_vin(db: Session) -> int:
    targets = build_rating_one_targets(db)
    if not targets:
        return 0

    total = 0
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .filter(_belarus_vin_check_listings_query_filter())
        .order_by(CarListing.created_at.desc())
    )
    for listing in query.yield_per(200):
        if not listing_matches_rating_one(listing, targets):
            continue
        if listing_has_saved_vin(listing):
            total += 1
    return total


def paginate_rating_one_listings_with_vin(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 100,
    date_filter: VinFoundDateFilter | None = None,
    import_filter: VinFoundImportFilter | None = None,
) -> tuple[list[CarListing], int]:
    targets = build_rating_one_targets(db)
    if not targets:
        return [], 0

    offset = max(page - 1, 0) * page_size
    active_import_filter = (import_filter or VinFoundImportFilter()).normalized()
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .filter(_belarus_vin_check_listings_query_filter())
        .order_by(CarListing.vin_fetched_at.desc().nullslast(), CarListing.created_at.desc())
    )

    if not active_import_filter.active:
        matched: list[CarListing] = []
        total = 0
        for listing in query.yield_per(200):
            if not listing_matches_rating_one(listing, targets):
                continue
            if not listing_has_saved_vin(listing):
                continue
            if not listing_matches_vin_found_date_filter(listing, date_filter):
                continue
            if total >= offset and len(matched) < page_size:
                matched.append(listing)
            total += 1
        return matched, total

    candidates: list[CarListing] = []
    for listing in query.yield_per(200):
        if not listing_matches_rating_one(listing, targets):
            continue
        if not listing_has_saved_vin(listing):
            continue
        if not listing_matches_vin_found_date_filter(listing, date_filter):
            continue
        candidates.append(listing)

    customs_map = build_listing_customs_map(db, candidates)
    filtered: list[CarListing] = []
    for listing in candidates:
        customs = customs_map.get(listing.id)
        release_date = (
            customs.release_date if customs and customs.found and customs.release_date else None
        )
        if listing_matches_vin_found_import_filter(release_date, active_import_filter):
            filtered.append(listing)

    total = len(filtered)
    return filtered[offset : offset + page_size], total


def list_rating_one_listings_with_vin(db: Session) -> list[CarListing]:
    listings, _ = paginate_rating_one_listings_with_vin(db, page=1, page_size=10**9)
    return listings


def build_vin_found_collection_stats_by_day(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Daily VIN collection stats for rating=1 found-VIN listings.

    Uses listing check date (vin_fetched_at, else created_at) and account labels,
    newest day first. When a date range is provided, every day in the range is
    included even if the count is zero.
    """
    listings, _ = paginate_rating_one_listings_with_vin(
        db,
        page=1,
        page_size=10**9,
        date_filter=VinFoundDateFilter(date_from=date_from, date_to=date_to),
    )
    account_labels = build_listing_vin_account_labels(db, listings)

    by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for listing in listings:
        checked_at = listing_vin_check_at(listing)
        if checked_at is None:
            continue
        checked_day = checked_at.date() if isinstance(checked_at, datetime) else checked_at
        day_key = checked_day.isoformat()
        label = account_labels.get(listing.id) or "Без аккаунта"
        by_day[day_key][label] += 1

    if date_from is not None or date_to is not None:
        start = date_from or date_to
        end = date_to or date_from
        assert start is not None and end is not None
        if (end - start).days > 89:
            start = end - timedelta(days=89)
        day_keys: list[str] = []
        cursor = start
        while cursor <= end:
            day_keys.append(cursor.isoformat())
            cursor += timedelta(days=1)
        day_keys.reverse()
    else:
        day_keys = sorted(by_day.keys(), reverse=True)

    groups: list[dict] = []
    for day_key in day_keys:
        account_counts = by_day.get(day_key, {})
        accounts = [
            {"id": None, "label": label, "count": count}
            for label, count in account_counts.items()
        ]
        accounts.sort(key=lambda row: (-row["count"], row["label"].casefold()))
        total = sum(row["count"] for row in accounts)
        try:
            day_label = date.fromisoformat(day_key).strftime("%d.%m.%Y")
        except ValueError:
            day_label = day_key
        groups.append(
            {
                "day": day_key,
                "day_label": day_label,
                "accounts": accounts,
                "total": total,
            }
        )
    return groups


def build_vin_found_collection_stats_by_account(
    db: Session,
    *,
    days: int = 30,
    today: date | None = None,
) -> list[dict]:
    """VIN collection totals per account for the last `days` days (inclusive)."""
    end = today or date.today()
    start = end - timedelta(days=max(days, 1) - 1)
    listings, _ = paginate_rating_one_listings_with_vin(
        db,
        page=1,
        page_size=10**9,
        date_filter=VinFoundDateFilter(date_from=start, date_to=end),
    )
    account_labels = build_listing_vin_account_labels(db, listings)
    counts: dict[str, int] = defaultdict(int)
    for listing in listings:
        label = account_labels.get(listing.id) or "Без аккаунта"
        counts[label] += 1
    rows = [
        {"label": label, "count": count}
        for label, count in counts.items()
    ]
    rows.sort(key=lambda row: (-row["count"], row["label"].casefold()))
    return rows


def listing_matches_vin_check_filters(
    listing: CarListing,
    filters: VinCheckListingFilters | None = None,
) -> bool:
    year = getattr(listing, "year", None)
    try:
        year_int = int(year) if year is not None else None
    except (TypeError, ValueError):
        year_int = None
    if year_int is None or year_int < VIN_CHECK_DEFAULT_YEAR_FROM:
        return False
    if filters is None:
        return True
    brand_filter = normalize_catalog_name(filters.brand)
    if brand_filter and normalize_catalog_name(getattr(listing, "brand", None)) != brand_filter:
        return False
    model_filter = normalize_catalog_name(filters.model)
    if model_filter and normalize_catalog_name(getattr(listing, "model", None)) != model_filter:
        return False
    if filters.only_automatic:
        if classify_transmission_slug(getattr(listing, "transmission_type", None)) == TRANSMISSION_SLUG_MANUAL:
            return False
    if filters.only_diesel:
        if classify_fuel_type(getattr(listing, "engine_type", None)) != FUEL_GROUP_DIESEL:
            return False
    if filters.year_from_2020:
        if year_int < 2020:
            return False
    if filters.mileage_to_100k or filters.mileage_to_200k:
        try:
            mileage_int = int(getattr(listing, "mileage", None) or 0)
        except (TypeError, ValueError):
            mileage_int = 0
        max_km = 100_000 if filters.mileage_to_100k else 200_000
        if mileage_int > max_km:
            return False
    return True


def paginate_rating_one_listings(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 21,
    filters: VinCheckListingFilters | None = None,
) -> tuple[list[CarListing], int]:
    targets = build_rating_one_targets(db)
    if not targets:
        return [], 0

    offset = max(page - 1, 0) * page_size
    sort = normalize_vin_check_sort(filters.sort if filters else None)
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .filter(_belarus_vin_check_listings_query_filter())
        .order_by(CarListing.created_at.desc())
    )

    if sort == VIN_CHECK_SORT_ADDED:
        matched: list[CarListing] = []
        total = 0
        for listing in query.yield_per(200):
            if not listing_matches_rating_one(listing, targets):
                continue
            if not listing_matches_vin_check_filters(listing, filters):
                continue
            if total >= offset and len(matched) < page_size:
                matched.append(listing)
            total += 1
        return matched, total

    candidates: list[CarListing] = []
    for listing in query.yield_per(200):
        if not listing_matches_rating_one(listing, targets):
            continue
        if not listing_matches_vin_check_filters(listing, filters):
            continue
        candidates.append(listing)

    if sort == VIN_CHECK_SORT_PRICE:
        candidates.sort(
            key=lambda row: (
                getattr(row, "price", None) is None,
                float(getattr(row, "price", None) or 0),
                -_listing_created_at_sort_value(row),
            )
        )
    elif sort == VIN_CHECK_SORT_MILEAGE:
        candidates.sort(
            key=lambda row: (
                getattr(row, "mileage", None) is None,
                int(getattr(row, "mileage", None) or 0),
                -_listing_created_at_sort_value(row),
            )
        )

    total = len(candidates)
    return candidates[offset : offset + page_size], total


def build_listing_customs_map(db: Session, listings: list[CarListing]) -> dict[int, ListingCustomsSummary]:
    vins = {(listing.id, (listing.vin or "").strip().upper()) for listing in listings}
    vin_values = {vin for _, vin in vins if len(vin) == 17}
    if not vin_values:
        return {}

    rows = (
        db.query(VinCustomsCheck)
        .filter(
            VinCustomsCheck.vin.in_(vin_values),
            VinCustomsCheck.database == DATABASE_PERSONAL,
        )
        .order_by(VinCustomsCheck.checked_at.desc())
        .all()
    )
    by_vin: dict[str, VinCustomsCheck] = {}
    for row in rows:
        if row.vin not in by_vin:
            by_vin[row.vin] = row

    result: dict[int, ListingCustomsSummary] = {}
    for listing_id, vin in vins:
        row = by_vin.get(vin)
        if row is None:
            continue
        result[listing_id] = ListingCustomsSummary(
            found=row.found,
            release_date=row.release_date,
            checked_at=row.checked_at,
            cached=True,
        )
    return result
