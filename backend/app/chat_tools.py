"""Chat tool definitions and executors (listings, market, catalog)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.body_type_labels import exclude_hidden_body_type
from app.listing_avg_prices import DEFAULT_MIN_SAMPLES
from app.listing_catalog_link import canonical_model_name, normalize_match_text
from app.listing_embeddings import search_similar
from app.models import CarListing, CatalogItem, ListingAvgPrice, ListingStatus

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "semantic_search_listings",
            "description": (
                "Семантический поиск опубликованных объявлений Auto160 по свободному тексту "
                "(например «Skoda Octavia автомат Минск»). Используй для подбора лотов по смыслу."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Поисковый запрос на русском"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": (
                "Фильтрованный поиск объявлений по марке, модели, городу, цене, году и мощности. "
                "Цены в BYN."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "model": {"type": "string"},
                    "city": {"type": "string"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "year_from": {"type": "integer"},
                    "year_to": {"type": "integer"},
                    "max_hp": {"type": "integer", "description": "Максимальная мощность, л.с."},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 15, "default": 8},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "market_avg",
            "description": (
                "Средняя рыночная цена (BYN) по марке/модели/году за окна 30/60/90/120 дней "
                "по данным Auto160. Нужны brand, model и year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "model": {"type": "string"},
                    "year": {"type": "integer"},
                    "window_days": {
                        "type": "integer",
                        "enum": [30, 60, 90, 120],
                        "description": "Если не указано — вернуть все окна",
                    },
                },
                "required": ["brand", "model", "year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_catalog",
            "description": (
                "Поиск комплектаций в каталоге Auto160 (до 160 л.с.) по марке и/или модели."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "make": {"type": "string"},
                    "model": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 10},
                },
            },
        },
    },
]


def _listing_card(listing: CarListing, *, distance: float | None = None) -> dict[str, Any]:
    card: dict[str, Any] = {
        "id": listing.id,
        "title": listing.title,
        "brand": listing.brand,
        "model": listing.model,
        "year": listing.year,
        "price_byn": float(listing.price) if listing.price is not None else None,
        "city": listing.city,
        "mileage": listing.mileage,
        "engine_power_hp": listing.engine_power_hp,
        "transmission_type": listing.transmission_type,
        "engine_type": listing.engine_type,
        "source": listing.source,
        "url": f"/listings/{listing.id}",
        "source_url": listing.source_url,
    }
    if distance is not None:
        card["distance"] = round(distance, 4)
    return card


def tool_semantic_search_listings(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    limit = min(max(int(args.get("limit") or 5), 1), 10)
    if not query:
        return {"items": [], "error": "query is required"}
    rows = search_similar(db, query, limit=limit)
    return {"items": [_listing_card(listing, distance=dist) for listing, dist in rows]}


def tool_search_listings(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(int(args.get("limit") or 8), 1), 15)
    query = exclude_hidden_body_type(db.query(CarListing), CarListing.body_type)
    query = query.filter(CarListing.status == ListingStatus.published)

    brand = (args.get("brand") or "").strip()
    model = (args.get("model") or "").strip()
    city = (args.get("city") or "").strip()
    if brand:
        query = query.filter(CarListing.brand.ilike(f"%{brand}%"))
    if model:
        query = query.filter(CarListing.model.ilike(f"%{model}%"))
    if city:
        query = query.filter(CarListing.city.ilike(f"%{city}%"))
    if args.get("min_price") is not None:
        query = query.filter(CarListing.price >= float(args["min_price"]))
    if args.get("max_price") is not None:
        query = query.filter(CarListing.price <= float(args["max_price"]))
    if args.get("year_from") is not None:
        query = query.filter(CarListing.year >= int(args["year_from"]))
    if args.get("year_to") is not None:
        query = query.filter(CarListing.year <= int(args["year_to"]))
    if args.get("max_hp") is not None:
        query = query.filter(CarListing.engine_power_hp <= int(args["max_hp"]))

    rows = query.order_by(desc(CarListing.created_at)).limit(limit).all()
    return {"items": [_listing_card(row) for row in rows], "count": len(rows)}


def tool_market_avg(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    from sqlalchemy import func

    brand = (args.get("brand") or "").strip()
    model = (args.get("model") or "").strip()
    year = args.get("year")
    if not brand or not model or year is None:
        return {"items": [], "error": "brand, model and year are required"}

    model_canon = canonical_model_name(model) or model
    q = (
        db.query(ListingAvgPrice)
        .filter(ListingAvgPrice.sample_count >= DEFAULT_MIN_SAMPLES)
        .filter(func.lower(ListingAvgPrice.brand) == normalize_match_text(brand))
        .filter(func.lower(ListingAvgPrice.model) == normalize_match_text(model_canon))
        .filter(ListingAvgPrice.year == int(year))
    )
    window = args.get("window_days")
    if window is not None:
        q = q.filter(ListingAvgPrice.window_days == int(window))

    rows = q.order_by(ListingAvgPrice.window_days.asc()).all()
    return {
        "items": [
            {
                "brand": row.brand,
                "model": row.model,
                "year": row.year,
                "window_days": row.window_days,
                "avg_price_byn": float(row.avg_price_byn),
                "min_price_byn": float(row.min_price_byn) if row.min_price_byn is not None else None,
                "max_price_byn": float(row.max_price_byn) if row.max_price_byn is not None else None,
                "sample_count": row.sample_count,
            }
            for row in rows
        ]
    }


def tool_lookup_catalog(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    limit = min(max(int(args.get("limit") or 10), 1), 20)
    make = (args.get("make") or "").strip()
    model = (args.get("model") or "").strip()
    q = db.query(CatalogItem).filter(CatalogItem.hidden_from_catalog.is_(False))
    if make:
        q = q.filter(CatalogItem.make.ilike(f"%{make}%"))
    if model:
        q = q.filter(CatalogItem.model.ilike(f"%{model}%"))
    if not make and not model:
        return {"items": [], "error": "provide make and/or model"}

    rows = (
        q.order_by(CatalogItem.make.asc(), CatalogItem.model.asc(), CatalogItem.year_from.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "make": row.make,
                "model": row.model,
                "generation": row.generation,
                "year_from": row.year_from,
                "year_to": row.year_to,
                "fuel_type": row.fuel_type,
                "engine_power_hp": row.engine_power_hp,
                "engine_volume_l": float(row.engine_volume_l) if row.engine_volume_l is not None else None,
                "transmission": row.transmission,
                "drivetrain": row.drivetrain,
                "body_type": row.body_type,
                "url": f"/catalog?make={row.make}",
            }
            for row in rows
        ]
    }


_DISPATCH = {
    "semantic_search_listings": tool_semantic_search_listings,
    "search_listings": tool_search_listings,
    "market_avg": tool_market_avg,
    "lookup_catalog": tool_lookup_catalog,
}


def run_tool(db: Session, name: str, arguments: str | dict[str, Any]) -> str:
    if isinstance(arguments, str):
        try:
            args = json.loads(arguments or "{}")
        except json.JSONDecodeError:
            args = {}
    else:
        args = arguments or {}
    handler = _DISPATCH.get(name)
    if handler is None:
        result: dict[str, Any] = {"error": f"unknown tool: {name}"}
    else:
        try:
            result = handler(db, args)
        except Exception as exc:  # noqa: BLE001
            result = {"error": str(exc)}
    return json.dumps(result, ensure_ascii=False)
