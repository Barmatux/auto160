"""Internal catalog ratings grouped by make / model / generation."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models import CatalogItem

RATING_CHOICES = (1, 2, 3)
RATING_FILTER_UNRATED = "unrated"
UNRATED_GENERATION_LABEL = "Без поколения"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class CatalogRatingRow:
    make: str
    model: str
    generation: str
    generation_key: str
    item_count: int
    rated_count: int
    rating: float | None
    mixed: bool
    hidden: bool
    mods_url: str
    production_years: str
    year_from: int | None
    year_to: int | None
    photo_item_id: int | None


def format_production_years(year_from: int | None, year_to: int | None) -> str:
    if year_from is None and year_to is None:
        return "—"
    start = str(year_from) if year_from is not None else "?"
    end = str(year_to) if year_to is not None else "?"
    return f"{start} – {end}"


def generation_key(value: str | None) -> str:
    return (value or "").strip()


def generation_label(value: str | None) -> str:
    key = generation_key(value)
    return key or UNRATED_GENERATION_LABEL


def format_rating(value: float | Decimal | None) -> str:
    if value is None:
        return ""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)


def parse_rating(raw: object) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float, Decimal)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(",", ".")
        if not text:
            return None
        value = float(text)
    if value <= 0 or value > 99:
        raise ValueError("Рейтинг должен быть числом от 1 до 99")
    return value


def parse_rating_filter_values(values: list[str] | None) -> tuple[frozenset[int], bool]:
    """Parse multi-value rating filter query params."""
    ratings: set[int] = set()
    include_unrated = False
    for raw in values or []:
        token = (raw or "").strip().lower()
        if not token:
            continue
        if token in {RATING_FILTER_UNRATED, "none", "unset", "null"}:
            include_unrated = True
            continue
        try:
            number = int(float(token.replace(",", ".")))
        except ValueError:
            continue
        if number in RATING_CHOICES:
            ratings.add(number)
    return frozenset(ratings), include_unrated


def rating_filter_tokens(ratings: frozenset[int], *, include_unrated: bool) -> list[str]:
    tokens = [str(value) for value in sorted(ratings)]
    if include_unrated:
        tokens.append(RATING_FILTER_UNRATED)
    return tokens


def _generation_filter(query, generation: str | None):
    key = generation_key(generation)
    if key and key != UNRATED_GENERATION_LABEL:
        return query.filter(CatalogItem.generation == key)
    return query.filter(or_(CatalogItem.generation.is_(None), CatalogItem.generation == ""))


def matching_catalog_items(db: Session, *, make: str, model: str, generation: str | None) -> list[CatalogItem]:
    make_name = (make or "").strip()
    model_name = (model or "").strip()
    if not make_name or not model_name:
        return []
    query = (
        db.query(CatalogItem)
        .filter(
            CatalogItem.source_site == "av.by",
            func.lower(CatalogItem.make) == make_name.lower(),
            func.lower(CatalogItem.model) == model_name.lower(),
        )
    )
    return _generation_filter(query, generation).order_by(CatalogItem.id.asc()).all()


def apply_generation_rating(
    db: Session,
    *,
    make: str,
    model: str,
    generation: str | None,
    rating: float | None,
) -> tuple[list[CatalogItem], int]:
    items = matching_catalog_items(db, make=make, model=model, generation=generation)
    for item in items:
        item.rating = rating
    return items, len(items)


def _grouped_query(
    db: Session,
    *,
    make: str | None = None,
    q: str | None = None,
    status: str = "all",
    rating_filters: frozenset[int] | None = None,
    include_unrated_rating: bool = False,
):
    query = (
        db.query(
            CatalogItem.make,
            CatalogItem.model,
            CatalogItem.generation,
            func.count(CatalogItem.id).label("item_count"),
            func.count(CatalogItem.rating).label("rated_count"),
            func.min(CatalogItem.rating).label("rating_min"),
            func.max(CatalogItem.rating).label("rating_max"),
            func.min(CatalogItem.year_from).label("year_from_min"),
            func.max(CatalogItem.year_to).label("year_to_max"),
            func.min(CatalogItem.id).label("first_item_id"),
            func.sum(case((CatalogItem.hidden_from_catalog.is_(True), 1), else_=0)).label("hidden_count"),
        )
        .filter(CatalogItem.source_site == "av.by")
        .group_by(CatalogItem.make, CatalogItem.model, CatalogItem.generation)
    )
    make_name = (make or "").strip()
    if make_name:
        query = query.filter(func.lower(CatalogItem.make) == make_name.lower())
    search = (q or "").strip()
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                CatalogItem.make.ilike(like),
                CatalogItem.model.ilike(like),
                CatalogItem.generation.ilike(like),
            )
        )
    if status == "rated":
        query = query.having(func.count(CatalogItem.rating) > 0)
    elif status == "unrated":
        query = query.having(func.count(CatalogItem.rating) == 0)
    if rating_filters or include_unrated_rating:
        parts = []
        if include_unrated_rating:
            parts.append(func.count(CatalogItem.rating) == 0)
        for rating_value in sorted(rating_filters or ()):
            parts.append(
                (func.count(CatalogItem.rating) > 0)
                & (func.min(CatalogItem.rating) <= rating_value)
                & (func.max(CatalogItem.rating) >= rating_value)
            )
        if parts:
            query = query.having(or_(*parts))
    return query


def list_catalog_makes(db: Session) -> list[str]:
    rows = (
        db.query(CatalogItem.make)
        .filter(CatalogItem.source_site == "av.by", CatalogItem.make.isnot(None))
        .distinct()
        .order_by(CatalogItem.make.asc())
        .all()
    )
    return [row[0] for row in rows if (row[0] or "").strip()]


def _row_from_group(row) -> CatalogRatingRow:
    rating_min = float(row.rating_min) if row.rating_min is not None else None
    rating_max = float(row.rating_max) if row.rating_max is not None else None
    mixed = bool(row.rated_count) and rating_min != rating_max
    rating = None if mixed or row.rated_count == 0 else rating_min
    make = (row.make or "").strip()
    model = (row.model or "").strip()
    key = generation_key(row.generation)
    params = {"make": make, "model": model}
    if key:
        params["generation"] = key
    item_count = int(row.item_count or 0)
    hidden_count = int(row.hidden_count or 0)
    year_from = int(row.year_from_min) if row.year_from_min is not None else None
    year_to = int(row.year_to_max) if row.year_to_max is not None else None
    photo_item_id = int(row.first_item_id) if row.first_item_id is not None else None
    return CatalogRatingRow(
        make=make,
        model=model,
        generation=generation_label(row.generation),
        generation_key=key,
        item_count=item_count,
        rated_count=int(row.rated_count or 0),
        rating=rating,
        mixed=mixed,
        hidden=item_count > 0 and hidden_count >= item_count,
        mods_url="/catalog/modifications?" + urlencode(params),
        production_years=format_production_years(year_from, year_to),
        year_from=year_from,
        year_to=year_to,
        photo_item_id=photo_item_id,
    )


def list_generation_ratings(
    db: Session,
    *,
    make: str | None = None,
    q: str | None = None,
    status: str = "all",
    rating_filters: frozenset[int] | None = None,
    include_unrated_rating: bool = False,
    page: int = 1,
    per_page: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[CatalogRatingRow], int]:
    page = max(page, 1)
    per_page = max(min(per_page, MAX_PAGE_SIZE), 1)
    grouped = _grouped_query(
        db,
        make=make,
        q=q,
        status=status,
        rating_filters=rating_filters,
        include_unrated_rating=include_unrated_rating,
    )
    total = db.query(func.count()).select_from(grouped.subquery()).scalar() or 0
    rows = (
        grouped.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.generation.asc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return [_row_from_group(row) for row in rows], int(total)
