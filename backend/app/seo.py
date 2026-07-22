"""SEO helpers: meta tags, robots.txt, sitemap.xml."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CarListing, CatalogItem, ListingStatus

SITE_NAME = "Auto160"
DEFAULT_DESCRIPTION = (
    "Auto160 — подбор авто до 160 л.с. в Беларуси: каталог комплектаций av.by, "
    "лента объявлений и проверка VIN в базе таможни ГТК."
)

NOINDEX_PREFIXES = (
    "/admin",
    "/login",
    "/register",
    "/logout",
    "/profile",
    "/create-listing",
)

STATIC_SEO: dict[str, tuple[str, str]] = {
    "/": (
        "Auto160 — подбор авто до 160 л.с.",
        DEFAULT_DESCRIPTION,
    ),
    "/catalog": (
        "Каталог авто до 160 л.с. — Auto160",
        "Комплектации автомобилей до 160 л.с.: марки, модели, поколения, характеристики и фото из каталога av.by.",
    ),
    "/listings": (
        "Лента объявлений — Auto160",
        "Актуальные объявления с av.by: цена, пробег, город, двигатель. Фильтры по марке, городу и проходным авто.",
    ),
    "/inspection": (
        "Проверка VIN в базе таможни РБ — Auto160",
        "Проверка VIN по базе ввезённого автотранспорта ГТК Беларуси перед покупкой автомобиля.",
    ),
}


@dataclass
class SeoMeta:
    title: str
    description: str
    path: str | None = None
    image: str | None = None
    noindex: bool | None = None


def _truncate(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def site_base_url(request: Request) -> str:
    configured = (settings.public_site_url or "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def absolute_url(base: str, url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/"):
        return f"{base}{url}"
    return f"{base}/{url}"


def _should_noindex(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in NOINDEX_PREFIXES)


def seo_meta_for_request(request: Request, meta: SeoMeta | None = None) -> SeoMeta:
    path = request.url.path
    if meta is not None:
        return meta
    if path in STATIC_SEO:
        title, description = STATIC_SEO[path]
        return SeoMeta(title=title, description=description, path=path)
    return SeoMeta(title=SITE_NAME, description=DEFAULT_DESCRIPTION, path=path)


def build_seo_context(request: Request, meta: SeoMeta | None = None) -> dict:
    resolved = seo_meta_for_request(request, meta)
    base = site_base_url(request)
    path = resolved.path or request.url.path
    canonical = f"{base}{path}"
    noindex = resolved.noindex if resolved.noindex is not None else _should_noindex(path)
    og_image = absolute_url(base, resolved.image) or f"{base}/static/og-default.svg"
    return {
        "seo_title": resolved.title,
        "seo_description": _truncate(resolved.description, 160),
        "seo_canonical": canonical,
        "seo_og_image": og_image,
        "seo_noindex": noindex,
        "site_base_url": base,
    }


def listing_seo_meta(listing: CarListing, *, cover_url: str | None = None) -> SeoMeta:
    hp_part = f", {listing.engine_power_hp} л.с." if listing.engine_power_hp else ""
    title = _truncate(
        f"{listing.brand} {listing.model} {listing.year}{hp_part} — {listing.city} — Auto160",
        70,
    )
    description = _truncate(
        f"{listing.title}. {listing.brand} {listing.model}, {listing.year} г., "
        f"{listing.mileage:,} км, {listing.city}. Цена {listing.price} ₽."
        .replace(",", " "),
        160,
    )
    return SeoMeta(
        title=title,
        description=description,
        path=f"/listings/{listing.id}",
        image=cover_url,
    )


def catalog_item_seo_meta(item: CatalogItem, *, cover_url: str | None = None) -> SeoMeta:
    generation = f", {item.generation}" if item.generation else ""
    hp_part = f", {item.engine_power_hp} л.с." if item.engine_power_hp else ""
    title = _truncate(f"{item.make} {item.model}{generation}{hp_part} — Auto160", 70)
    years = ""
    if item.year_from or item.year_to:
        years = f" Годы: {item.year_from or '?'}–{item.year_to or '?'}."
    description = _truncate(
        f"Комплектация {item.make} {item.model}{generation}.{years} "
        f"Характеристики, фото и связанные объявления на Auto160.",
        160,
    )
    return SeoMeta(
        title=title,
        description=description,
        path=f"/catalog/item/{item.id}",
        image=cover_url,
    )


def catalog_models_seo_meta(make: str | None, *, total: int) -> SeoMeta:
    if make:
        title = f"Модели {make} до 160 л.с. — Auto160"
        description = f"Модели {make} до 160 л.с. в каталоге Auto160. Найдено: {total}."
        path = f"/catalog/models?make={quote(make)}"
    else:
        title = "Все модели — Auto160"
        description = f"Модели автомобилей до 160 л.с. в каталоге Auto160. Найдено: {total}."
        path = "/catalog/models"
    return SeoMeta(title=title, description=description, path=path)


def catalog_generations_seo_meta(make: str | None, model: str | None, *, total: int) -> SeoMeta:
    if make and model:
        title = f"Поколения {make} {model} — Auto160"
        description = f"Поколения {make} {model} до 160 л.с. Найдено: {total}."
        path = f"/catalog/generations?make={quote(make)}&model={quote(model)}"
    else:
        title = "Поколения — Auto160"
        description = f"Поколения автомобилей до 160 л.с. Найдено: {total}."
        path = "/catalog/generations"
    return SeoMeta(title=title, description=description, path=path)


def catalog_modifications_seo_meta(
    make: str | None,
    model: str | None,
    generation: str | None,
    *,
    total: int,
) -> SeoMeta:
    parts = [part for part in (make, model, generation) if part]
    label = " ".join(parts) if parts else "Комплектации"
    title = f"{label} — Auto160"
    description = f"Комплектации {label} до 160 л.с. Найдено: {total}."
    query: list[str] = []
    if make:
        query.append(f"make={quote(make)}")
    if model:
        query.append(f"model={quote(model)}")
    if generation:
        query.append(f"generation={quote(generation)}")
    path = "/catalog/modifications"
    if query:
        path = f"{path}?{'&'.join(query)}"
    return SeoMeta(title=title, description=description, path=path)


def build_robots_txt(base_url: str) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /api/",
            "Disallow: /login",
            "Disallow: /register",
            "Disallow: /logout",
            "Disallow: /profile/",
            "Disallow: /create-listing",
            "",
            f"Sitemap: {base_url}/sitemap.xml",
            "",
        ]
    )


def _hp_filter():
    return or_(CatalogItem.engine_power_hp.is_(None), CatalogItem.engine_power_hp <= 160)


def _format_lastmod(value: datetime | None) -> str:
    if value is None:
        return datetime.now(UTC).strftime("%Y-%m-%d")
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%d")


def build_sitemap_entries(db: Session, base_url: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    for path in ("/", "/catalog", "/listings", "/inspection"):
        entries.append((f"{base_url}{path}", today))

    makes = (
        db.query(CatalogItem.make)
        .filter(CatalogItem.source_site == "av.by", CatalogItem.make.isnot(None), _hp_filter())
        .distinct()
        .order_by(CatalogItem.make.asc())
        .all()
    )
    for (make,) in makes:
        if not make:
            continue
        entries.append((f"{base_url}/catalog/models?make={quote(make.strip())}", today))

    listings = (
        db.query(CarListing.id, CarListing.created_at)
        .filter(CarListing.status == ListingStatus.published)
        .order_by(CarListing.id.asc())
        .all()
    )
    for listing_id, created_at in listings:
        entries.append((f"{base_url}/listings/{listing_id}", _format_lastmod(created_at)))

    catalog_items = (
        db.query(CatalogItem.id, CatalogItem.created_at)
        .filter(CatalogItem.source_site == "av.by", _hp_filter())
        .order_by(CatalogItem.id.asc())
        .all()
    )
    for item_id, created_at in catalog_items:
        entries.append((f"{base_url}/catalog/item/{item_id}", _format_lastmod(created_at)))

    return entries


def render_sitemap_xml(entries: list[tuple[str, str]]) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in entries:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{loc}</loc>",
                f"    <lastmod>{lastmod}</lastmod>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"
