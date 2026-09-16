"""Auto-fetch VIN and customs data for listings tied to catalog rating=1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.avby_offer_metadata import fetch_and_apply_offer_vin_metadata
from app.avby_vin import AvbyVinError, get_or_fetch_listing_vin
from app.customs_vin import DATABASE_PERSONAL, CustomsVinError, has_fresh_customs_check, lookup_customs_vin
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
) -> tuple[list[CarListing], int]:
    targets = build_rating_one_targets(db)
    if not targets:
        return [], 0

    offset = max(page - 1, 0) * page_size
    matched: list[CarListing] = []
    total = 0
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .order_by(CarListing.vin_fetched_at.desc().nullslast(), CarListing.created_at.desc())
    )
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


def listing_matches_vin_check_filters(
    listing: CarListing,
    filters: VinCheckListingFilters | None = None,
) -> bool:
    if filters is None:
        return True
    if filters.only_automatic:
        if classify_transmission_slug(getattr(listing, "transmission_type", None)) == TRANSMISSION_SLUG_MANUAL:
            return False
    if filters.only_diesel:
        if classify_fuel_type(getattr(listing, "engine_type", None)) != FUEL_GROUP_DIESEL:
            return False
    if filters.year_from_2020:
        year = getattr(listing, "year", None)
        if year is None or int(year) < 2020:
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
    matched: list[CarListing] = []
    total = 0
    query = (
        db.query(CarListing)
        .filter(CarListing.status == ListingStatus.published)
        .order_by(CarListing.created_at.desc())
    )
    for listing in query.yield_per(200):
        if not listing_matches_rating_one(listing, targets):
            continue
        if not listing_matches_vin_check_filters(listing, filters):
            continue
        if total >= offset and len(matched) < page_size:
            matched.append(listing)
        total += 1
    return matched, total


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
