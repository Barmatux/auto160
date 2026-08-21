"""SEO helpers: meta tags, robots.txt, sitemap.xml, JSON-LD."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.body_type_labels import exclude_hidden_body_type
from app.models import CarListing, CatalogItem, ListingStatus

SITE_NAME = "Auto160"
DEFAULT_DESCRIPTION = (
    "Auto160 — подбор авто до 160 л.с. в Беларуси: каталог комплектаций av.by, "
    "лента объявлений и проверка VIN в базе таможни ГТК."
)

# City landings that are allowed to be indexed (unique title/H1/canonical).
INDEXABLE_CITIES = frozenset({"Минск", "Гродно", "Брест", "Гомель"})

NOINDEX_PREFIXES = (
    "/admin",
    "/login",
    "/register",
    "/logout",
    "/profile",
    "/create-listing",
    "/design-preview",
    "/catalog/compare",
)

STATIC_SEO: dict[str, tuple[str, str]] = {
    "/": (
        "Auto160 — подбор авто до 160 л.с.",
        DEFAULT_DESCRIPTION,
    ),
    "/catalog": (
        "Каталог авто до 160 л.с. — Auto160",
        "Комплектации автомобилей до 160 л.с.: марки, модели, поколения, характеристики и фото.",
    ),
    "/listings": (
        "Лента объявлений до 160 л.с. в Беларуси — Auto160",
        "Актуальные объявления автомобилей до 160 л.с. в Беларуси: цена, пробег, город, двигатель.",
    ),
    "/inspection": (
        "Проверка VIN в базе таможни РБ — Auto160",
        "Проверка VIN по базе ввезённого автотранспорта ГТК Беларуси перед покупкой автомобиля.",
    ),
    "/guides/vin": (
        "Проверка VIN и таможня РБ: как пользоваться — Auto160",
        "Как проверить VIN автомобиля в Беларуси: база ГТК, что смотреть в отчёте и как не купить проблемное авто.",
    ),
    "/guides/do-160-hp": (
        "Зачем выбирать авто до 160 л.с. в Беларуси — Auto160",
        "Почему порог 160 л.с. важен при выборе авто в Беларуси: налоги, страховка, эксплуатация и подбор на Auto160.",
    ),
}


@dataclass
class SeoMeta:
    title: str
    description: str
    path: str | None = None
    image: str | None = None
    noindex: bool | None = None
    json_ld: list[dict[str, Any]] = field(default_factory=list)
    h1: str | None = None
    intro: str | None = None


def _truncate(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def site_base_url(request: Request | None = None) -> str:
    configured = (settings.public_site_url or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        return str(request.base_url).rstrip("/")
    return "https://auto160.by"


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


def dumps_json_ld(blocks: list[dict[str, Any]]) -> str:
    return json.dumps(blocks, ensure_ascii=False, separators=(",", ":"))


def organization_json_ld(base: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": SITE_NAME,
        "url": base,
        "logo": f"{base}/static/favicon.svg",
        "description": DEFAULT_DESCRIPTION,
    }


def website_json_ld(base: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": base,
        "description": DEFAULT_DESCRIPTION,
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": base},
    }


def breadcrumb_json_ld(base: str, crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    elements = []
    for index, (name, path) in enumerate(crumbs, start=1):
        item = absolute_url(base, path) or f"{base}/"
        elements.append(
            {
                "@type": "ListItem",
                "position": index,
                "name": name,
                "item": item,
            }
        )
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": elements,
    }


def listing_offer_json_ld(
    listing: CarListing,
    *,
    base: str,
    cover_url: str | None = None,
) -> dict[str, Any]:
    url = f"{base}/listings/{listing.id}"
    image = absolute_url(base, cover_url)
    vehicle: dict[str, Any] = {
        "@type": "Car",
        "name": f"{listing.brand} {listing.model} {listing.year}",
        "brand": {"@type": "Brand", "name": listing.brand},
        "model": listing.model,
        "vehicleModelDate": str(listing.year) if listing.year else None,
        "mileageFromOdometer": {
            "@type": "QuantitativeValue",
            "value": listing.mileage,
            "unitCode": "KMT",
        }
        if listing.mileage is not None
        else None,
        "vehicleEngine": {
            "@type": "EngineSpecification",
            "enginePower": {
                "@type": "QuantitativeValue",
                "value": listing.engine_power_hp,
                "unitCode": "BHP",
            },
        }
        if listing.engine_power_hp
        else None,
        "vehicleTransmission": listing.transmission_type,
        "driveWheelConfiguration": listing.drive_type,
        "bodyType": listing.body_type,
        "vehicleIdentificationNumber": listing.vin if listing.vin_indicated and listing.vin else None,
        "image": image,
        "url": url,
    }
    vehicle = {k: v for k, v in vehicle.items() if v is not None}
    offer: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Offer",
        "url": url,
        "priceCurrency": "RUB",
        "price": str(listing.price) if listing.price is not None else None,
        "availability": "https://schema.org/InStock",
        "itemOffered": vehicle,
        "areaServed": listing.city,
    }
    return {k: v for k, v in offer.items() if v is not None}


def catalog_item_json_ld(
    item: CatalogItem,
    *,
    base: str,
    cover_url: str | None = None,
) -> dict[str, Any]:
    url = f"{base}/catalog/item/{item.id}"
    name_parts = [item.make, item.model]
    if item.generation:
        name_parts.append(item.generation)
    payload: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": " ".join(p for p in name_parts if p),
        "brand": {"@type": "Brand", "name": item.make},
        "model": item.model,
        "url": url,
        "image": absolute_url(base, cover_url),
        "description": _truncate(
            f"Комплектация {item.make} {item.model}"
            + (f" {item.generation}" if item.generation else "")
            + " до 160 л.с. на Auto160.",
            160,
        ),
    }
    if item.engine_power_hp:
        payload["additionalProperty"] = [
            {
                "@type": "PropertyValue",
                "name": "enginePowerHp",
                "value": item.engine_power_hp,
            }
        ]
    return {k: v for k, v in payload.items() if v is not None}


def faq_page_json_ld(base: str, path: str, questions: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "url": f"{base}{path}",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in questions
        ],
    }


def article_json_ld(base: str, path: str, title: str, description: str) -> dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "url": f"{base}{path}",
        "author": {"@type": "Organization", "name": SITE_NAME},
        "publisher": {"@type": "Organization", "name": SITE_NAME, "url": base},
    }


def build_seo_context(request: Request, meta: SeoMeta | None = None) -> dict:
    resolved = seo_meta_for_request(request, meta)
    base = site_base_url(request)
    path = resolved.path or request.url.path
    canonical = f"{base}{path}" if path.startswith("/") else f"{base}/{path}"
    noindex = resolved.noindex if resolved.noindex is not None else _should_noindex(request.url.path)
    og_image = absolute_url(base, resolved.image) or f"{base}/static/og-default.svg"
    return {
        "seo_title": resolved.title,
        "seo_description": _truncate(resolved.description, 160),
        "seo_canonical": canonical,
        "seo_og_image": og_image,
        "seo_noindex": noindex,
        "site_base_url": base,
        "seo_json_ld": resolved.json_ld,
        "seo_json_ld_script": dumps_json_ld(resolved.json_ld) if resolved.json_ld else None,
        "seo_h1": resolved.h1,
        "seo_intro": resolved.intro,
    }


def home_seo_meta(request: Request) -> SeoMeta:
    base = site_base_url(request)
    title, description = STATIC_SEO["/"]
    return SeoMeta(
        title=title,
        description=description,
        path="/",
        json_ld=[organization_json_ld(base), website_json_ld(base)],
        h1="Подбор авто до 160 л.с. в Беларуси",
    )


def listing_seo_meta(
    listing: CarListing,
    *,
    cover_url: str | None = None,
    base: str | None = None,
) -> SeoMeta:
    resolved_base = (base or "").rstrip("/") or "https://auto160.by"
    hp_part = f", {listing.engine_power_hp} л.с." if listing.engine_power_hp else ""
    title = _truncate(
        f"{listing.brand} {listing.model} {listing.year}{hp_part} — {listing.city} — Auto160",
        70,
    )
    description = _truncate(
        f"{listing.title}. {listing.brand} {listing.model}, {listing.year} г., "
        f"{listing.mileage:,} км, {listing.city}. Цена {listing.price} ₽.".replace(",", " "),
        160,
    )
    crumbs = [
        ("Главная", "/"),
        ("Лента объявлений", "/listings"),
        (f"{listing.brand} {listing.model}", f"/listings/{listing.id}"),
    ]
    return SeoMeta(
        title=title,
        description=description,
        path=f"/listings/{listing.id}",
        image=cover_url,
        json_ld=[
            breadcrumb_json_ld(resolved_base, crumbs),
            listing_offer_json_ld(listing, base=resolved_base, cover_url=cover_url),
        ],
    )


def catalog_item_seo_meta(
    item: CatalogItem,
    *,
    cover_url: str | None = None,
    base: str | None = None,
) -> SeoMeta:
    resolved_base = (base or "").rstrip("/") or "https://auto160.by"
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
    crumbs = [("Главная", "/"), ("Каталог", "/catalog")]
    if item.make:
        crumbs.append((item.make, f"/catalog/models?make={quote(item.make)}"))
    if item.make and item.model:
        crumbs.append(
            (
                item.model,
                f"/catalog/generations?make={quote(item.make)}&model={quote(item.model)}",
            )
        )
    crumbs.append((title.split(" — ")[0], f"/catalog/item/{item.id}"))
    return SeoMeta(
        title=title,
        description=description,
        path=f"/catalog/item/{item.id}",
        image=cover_url,
        json_ld=[
            breadcrumb_json_ld(resolved_base, crumbs),
            catalog_item_json_ld(item, base=resolved_base, cover_url=cover_url),
        ],
        h1=f"{item.make} {item.model}{generation} до 160 л.с.",
        intro=(
            f"Характеристики комплектации {item.make} {item.model}"
            f"{generation} в каталоге Auto160 — подбор авто до 160 л.с. в Беларуси."
        ),
    )


def catalog_models_seo_meta(make: str | None, *, total: int) -> SeoMeta:
    if make:
        title = f"Модели {make} под льготный утильсбор (до 160 л.с.) — Auto160"
        description = (
            f"Модели {make} под льготный утильсбор (до 160 л.с.) в каталоге Auto160: поколения, "
            f"комплектации и объявления. Найдено моделей: {total}."
        )
        path = f"/catalog/models?make={quote(make)}"
        h1 = f"Модели {make} под льготный утильсбор (до 160 л.с.)"
        intro = (
            f"Выберите модель {make} под льготный утильсбор (до 160 л.с.): сравните поколения и "
            f"перейдите к актуальным объявлениям в Беларуси."
        )
        noindex = False
    else:
        title = "Все модели под льготный утильсбор (до 160 л.с.) — Auto160"
        description = f"Модели автомобилей до 160 л.с. в каталоге Auto160. Найдено: {total}."
        path = "/catalog/models"
        h1 = "Все модели под льготный утильсбор (до 160 л.с.)"
        intro = "Каталог моделей под льготный утильсбор (до 160 л.с.) для рынка Беларуси."
        noindex = True
    return SeoMeta(
        title=title,
        description=description,
        path=path,
        noindex=noindex,
        h1=h1,
        intro=intro,
    )


def catalog_generations_seo_meta(make: str | None, model: str | None, *, total: int) -> SeoMeta:
    if make and model:
        title = f"Поколения {make} {model} до 160 л.с. — Auto160"
        description = (
            f"Поколения {make} {model} до 160 л.с.: годы выпуска, комплектации и объявления. "
            f"Найдено: {total}."
        )
        path = f"/catalog/generations?make={quote(make)}&model={quote(model)}"
        h1 = f"Поколения {make} {model} до 160 л.с."
        intro = (
            f"Сравните поколения {make} {model} до 160 л.с. и перейдите к комплектациям "
            f"и объявлениям в Беларуси."
        )
        noindex = False
    else:
        title = "Поколения — Auto160"
        description = f"Поколения автомобилей до 160 л.с. Найдено: {total}."
        path = "/catalog/generations"
        h1 = "Поколения автомобилей"
        intro = None
        noindex = True
    return SeoMeta(
        title=title,
        description=description,
        path=path,
        noindex=noindex,
        h1=h1,
        intro=intro,
    )


def catalog_modifications_seo_meta(
    make: str | None,
    model: str | None,
    generation: str | None,
    *,
    total: int,
    extra_filters: bool = False,
) -> SeoMeta:
    parts = [part for part in (make, model, generation) if part]
    label = " ".join(parts) if parts else "Комплектации"
    if make and model:
        title = f"{label} до 160 л.с. — Auto160"
        description = (
            f"Комплектации {label} до 160 л.с.: характеристики, фото и объявления. Найдено: {total}."
        )
        h1 = f"{label} до 160 л.с. в Беларуси"
        intro = (
            f"Подбор комплектаций {label} с мощностью до 160 л.с. — сравните параметры "
            f"и смотрите связанные объявления."
        )
        noindex = extra_filters
    else:
        title = f"{label} — Auto160"
        description = f"Комплектации {label} до 160 л.с. Найдено: {total}."
        h1 = label
        intro = None
        noindex = True
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
    return SeoMeta(
        title=title,
        description=description,
        path=path,
        noindex=noindex,
        h1=h1,
        intro=intro,
    )


def listings_feed_seo_meta(
    *,
    city: str | None = None,
    brand: str | None = None,
    model: str | None = None,
    page: int = 1,
    total: int = 0,
    noisy_filters: bool = False,
) -> SeoMeta:
    """Build SEO for /listings. Only clean city or brand(+model) landings are indexed."""
    indexable_city = bool(city and city in INDEXABLE_CITIES and not brand and not noisy_filters and page == 1)
    indexable_brand = bool(brand and not city and not noisy_filters and page == 1)

    if indexable_city:
        title = f"Авто до 160 л.с. в городе {city} — Auto160"
        description = (
            f"Объявления автомобилей до 160 л.с. в городе {city}: цена, пробег, двигатель. "
            f"Сейчас в ленте: {total}."
        )
        path = f"/listings?city={quote(city)}"
        h1 = f"Авто до 160 л.с. в городе {city}"
        intro = (
            f"Актуальные объявления машин до 160 л.с. в городе {city}. "
            f"Сравнивайте комплектации в каталоге и проверяйте VIN перед покупкой."
        )
        return SeoMeta(
            title=title,
            description=description,
            path=path,
            noindex=False,
            h1=h1,
            intro=intro,
        )

    if indexable_brand:
        label = f"{brand} {model}".strip() if model else brand
        title = f"{label} до 160 л.с. — объявления — Auto160"
        description = (
            f"Объявления {label} до 160 л.с. в Беларуси. Найдено: {total}."
        )
        params = [("brand", brand)]
        if model:
            params.append(("model", model))
        path = "/listings?" + urlencode(params)
        h1 = f"{label} до 160 л.с. — объявления"
        intro = f"Лента объявлений {label} с ограничением по мощности до 160 л.с."
        return SeoMeta(
            title=title,
            description=description,
            path=path,
            noindex=False,
            h1=h1,
            intro=intro,
        )

    title, description = STATIC_SEO["/listings"]
    noindex = bool(noisy_filters or page > 1 or city or brand)
    return SeoMeta(
        title=title,
        description=description,
        path="/listings",
        noindex=noindex if (noisy_filters or page > 1 or city or brand) else False,
        h1="Лента объявлений до 160 л.с.",
        intro=(
            "Актуальные объявления автомобилей до 160 л.с. в Беларуси: фильтруйте по марке, "
            "городу и проходным годам."
        ),
    )


def inspection_seo_meta(*, has_query: bool) -> SeoMeta:
    title, description = STATIC_SEO["/inspection"]
    return SeoMeta(
        title=title,
        description=description,
        path="/inspection",
        noindex=has_query,
        h1="Проверка VIN в базе таможни РБ",
    )


def guide_vin_seo_meta(base: str) -> SeoMeta:
    title, description = STATIC_SEO["/guides/vin"]
    faq = [
        (
            "Что проверяет Auto160 по VIN?",
            "Сервис обращается к данным о ввезённом автотранспорте и показывает сведения, "
            "доступные по VIN в контексте таможни Республики Беларусь.",
        ),
        (
            "Заменяет ли проверка отчёт дилера или нотариуса?",
            "Нет. Это быстрый предварительный контроль перед осмотром и сделкой, а не юридическая экспертиза.",
        ),
        (
            "Нужен ли полный VIN из 17 символов?",
            "Да. Без полного корректного VIN проверка невозможна — символы I, O и Q в VIN не используются.",
        ),
    ]
    return SeoMeta(
        title=title,
        description=description,
        path="/guides/vin",
        json_ld=[
            article_json_ld(base, "/guides/vin", title, description),
            faq_page_json_ld(base, "/guides/vin", faq),
            breadcrumb_json_ld(base, [("Главная", "/"), ("Гайды", "/guides/vin"), ("Проверка VIN", "/guides/vin")]),
        ],
        h1="Проверка VIN и таможня РБ",
    )


def guide_do_160_seo_meta(base: str) -> SeoMeta:
    title, description = STATIC_SEO["/guides/do-160-hp"]
    return SeoMeta(
        title=title,
        description=description,
        path="/guides/do-160-hp",
        json_ld=[
            article_json_ld(base, "/guides/do-160-hp", title, description),
            breadcrumb_json_ld(
                base,
                [("Главная", "/"), ("Гайды", "/guides/do-160-hp"), ("До 160 л.с.", "/guides/do-160-hp")],
            ),
        ],
        h1="Зачем выбирать авто до 160 л.с. в Беларуси",
    )


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
            "Disallow: /design-preview",
            "Disallow: /catalog/compare",
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

    for path in (
        "/",
        "/catalog",
        "/listings",
        "/inspection",
        "/guides/vin",
        "/guides/do-160-hp",
    ):
        entries.append((f"{base_url}{path}", today))

    for city in sorted(INDEXABLE_CITIES):
        count = (
            db.query(func.count(CarListing.id))
            .filter(CarListing.status == ListingStatus.published, CarListing.city == city)
            .scalar()
            or 0
        )
        if count > 0:
            entries.append((f"{base_url}/listings?city={quote(city)}", today))

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
        make = make.strip()
        entries.append((f"{base_url}/catalog/models?make={quote(make)}", today))

        model_rows = (
            db.query(CatalogItem.model)
            .filter(
                CatalogItem.source_site == "av.by",
                CatalogItem.make == make,
                CatalogItem.model.isnot(None),
                _hp_filter(),
            )
            .distinct()
            .order_by(CatalogItem.model.asc())
            .all()
        )
        for (model,) in model_rows:
            if not model:
                continue
            model = model.strip()
            entries.append(
                (
                    f"{base_url}/catalog/generations?make={quote(make)}&model={quote(model)}",
                    today,
                )
            )
            gen_rows = (
                db.query(CatalogItem.generation)
                .filter(
                    CatalogItem.source_site == "av.by",
                    CatalogItem.make == make,
                    CatalogItem.model == model,
                    CatalogItem.generation.isnot(None),
                    _hp_filter(),
                )
                .distinct()
                .order_by(CatalogItem.generation.asc())
                .all()
            )
            for (generation,) in gen_rows:
                if not generation:
                    continue
                entries.append(
                    (
                        f"{base_url}/catalog/modifications?"
                        f"make={quote(make)}&model={quote(model)}&generation={quote(generation.strip())}",
                        today,
                    )
                )
            # Also include make+model modifications without generation (landing).
            entries.append(
                (
                    f"{base_url}/catalog/modifications?make={quote(make)}&model={quote(model)}",
                    today,
                )
            )

    listings = (
        exclude_hidden_body_type(
            db.query(CarListing.id, CarListing.created_at).filter(CarListing.status == ListingStatus.published),
            CarListing.body_type,
        )
        .order_by(CarListing.id.asc())
        .all()
    )
    for listing_id, created_at in listings:
        entries.append((f"{base_url}/listings/{listing_id}", _format_lastmod(created_at)))

    catalog_items = (
        exclude_hidden_body_type(
            db.query(CatalogItem.id, CatalogItem.created_at).filter(CatalogItem.source_site == "av.by", _hp_filter()),
            CatalogItem.body_type,
        )
        .order_by(CatalogItem.id.asc())
        .all()
    )
    for item_id, created_at in catalog_items:
        entries.append((f"{base_url}/catalog/item/{item_id}", _format_lastmod(created_at)))

    return entries


def render_sitemap_xml(entries: list[tuple[str, str]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
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
