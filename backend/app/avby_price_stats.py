"""Fetch and persist av.by ocenka / price-statistics for catalog generations."""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlencode

from curl_cffi import requests
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.avby_session import AVBY_PUBLIC_API_KEY
from app.models import (
    AvbyPriceHistoryPoint,
    AvbyPriceSoldAdvert,
    AvbyPriceStatTarget,
    AvbyPriceYearStat,
    CatalogItem,
)

logger = logging.getLogger(__name__)

API_BASE = "https://api.av.by"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_CATALOG_SLUG_RE = re.compile(r"/catalog/([^/?#]+)", re.I)


@dataclass
class SoftRateLimit:
    """Adaptive delay between public API calls to reduce WAF risk."""

    min_delay: float = 4.0
    max_delay: float = 8.0
    backoff: float = 0.0
    max_backoff: float = 600.0

    def wait(self) -> None:
        delay = random.uniform(self.min_delay, self.max_delay) + self.backoff
        time.sleep(delay)

    def on_success(self) -> None:
        self.backoff = max(0.0, self.backoff * 0.5)

    def on_rate_limit(self) -> None:
        self.backoff = min(self.max_backoff, max(45.0, self.backoff * 2 or 60.0))
        logger.warning("avby price-stats rate limited; backoff=%.0fs", self.backoff)
        time.sleep(self.backoff)


class AvbyPriceStatsClient:
    def __init__(self, *, rate: SoftRateLimit | None = None) -> None:
        self.rate = rate or SoftRateLimit()
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://av.by",
            "Referer": "https://av.by/ocenka-avto",
            "X-Api-Key": AVBY_PUBLIC_API_KEY,
            "api-key": AVBY_PUBLIC_API_KEY,
            "x-device-type": "web.desktop",
        }

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{API_BASE}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        for attempt in range(8):
            self.rate.wait()
            try:
                resp = self.session.get(
                    url,
                    headers=self._headers(),
                    impersonate="chrome124",
                    timeout=45,
                )
            except Exception as exc:
                logger.warning("avby price-stats network error attempt=%s %s", attempt + 1, exc)
                self.rate.on_rate_limit()
                continue
            if resp.status_code == 429 or resp.status_code == 503:
                self.rate.on_rate_limit()
                continue
            if resp.status_code >= 500:
                logger.warning("avby price-stats HTTP %s attempt=%s", resp.status_code, attempt + 1)
                self.rate.on_rate_limit()
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code} for {url}: {resp.text[:300]}")
            self.rate.on_success()
            payload = resp.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"Unexpected JSON for {url}")
            return payload
        raise RuntimeError(f"Gave up after retries: {url}")


def catalog_slug_from_url(source_url: str | None) -> str | None:
    if not source_url:
        return None
    match = _CATALOG_SLUG_RE.search(source_url)
    return match.group(1) if match else None


def _normalize_makes(makes: list[str] | None) -> list[str] | None:
    if not makes:
        return None
    cleaned = [m.strip() for m in makes if m and m.strip()]
    return cleaned or None


def build_catalog_generation_rows(
    db: Session,
    *,
    makes: list[str] | None = None,
    rating_one_only: bool = True,
    arbitrage_track_only: bool = False,
) -> list[dict[str, Any]]:
    """Group CatalogItem modifications into generation-level ocenka targets.

    Default: rating=1 only (existing analytics set).
    With ``makes``: all generations for those brands (rating filter off unless
    ``rating_one_only=True`` is passed explicitly).
    With ``arbitrage_track_only``: generations marked «Аналитика РБ».
    """
    makes = _normalize_makes(makes)
    q = db.query(CatalogItem).filter(
        (CatalogItem.source_site == "av.by")
        | (CatalogItem.source_url.ilike("%av.by/catalog/%"))
    )
    if arbitrage_track_only:
        q = q.filter(CatalogItem.arbitrage_track.is_(True))
    elif rating_one_only:
        q = q.filter(CatalogItem.rating == 1)
    if makes:
        q = q.filter(or_(*[CatalogItem.make.ilike(m) for m in makes]))
    items = q.all()
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        slug = catalog_slug_from_url(item.source_url)
        if not slug:
            continue
        y_from = int(item.year_from) if item.year_from else None
        y_to = int(item.year_to) if item.year_to else None
        # Prefer generation URL without /modification/… for landing resolve.
        source_url = item.source_url or ""
        gen_url_match = re.search(r"(https?://[^/]+/catalog/[^/]+)", source_url, re.I)
        gen_url = gen_url_match.group(1) if gen_url_match else source_url
        row = grouped.get(slug)
        if row is None:
            grouped[slug] = {
                "catalog_slug": slug,
                "make": (item.make or "").strip(),
                "model": (item.model or "").strip(),
                "generation": (item.generation or "").strip() or None,
                "year_from": y_from,
                "year_to": y_to,
                "source_url": gen_url,
            }
            continue
        if y_from is not None:
            row["year_from"] = (
                min(row["year_from"], y_from) if row["year_from"] is not None else y_from
            )
        if y_to is not None:
            row["year_to"] = (
                max(row["year_to"], y_to) if row["year_to"] is not None else y_to
            )
        if not row.get("source_url") and gen_url:
            row["source_url"] = gen_url
    return sorted(grouped.values(), key=lambda r: (r["make"], r["model"], r["catalog_slug"]))


def build_rating_one_generation_rows(db: Session) -> list[dict[str, Any]]:
    return build_catalog_generation_rows(db, rating_one_only=True)


def upsert_targets_from_catalog(
    db: Session,
    *,
    makes: list[str] | None = None,
    rating_one_only: bool | None = None,
    arbitrage_track_only: bool = False,
) -> int:
    makes = _normalize_makes(makes)
    if rating_one_only is None:
        # Brand dumps / tracked dumps include every matching generation;
        # otherwise keep the historical rating=1 analytics set.
        rating_one_only = not bool(makes) and not arbitrage_track_only
    rows = build_catalog_generation_rows(
        db,
        makes=makes,
        rating_one_only=rating_one_only,
        arbitrage_track_only=arbitrage_track_only,
    )
    existing = {
        t.catalog_slug: t for t in db.query(AvbyPriceStatTarget).all()
    }
    created = 0
    for row in rows:
        target = existing.get(row["catalog_slug"])
        if target is None:
            target = AvbyPriceStatTarget(**row, resolve_status="pending")
            db.add(target)
            created += 1
            continue
        target.make = row["make"]
        target.model = row["model"]
        target.generation = row["generation"]
        target.year_from = row["year_from"]
        target.year_to = row["year_to"]
        target.source_url = row["source_url"]
        target.updated_at = datetime.utcnow()
    db.commit()
    return created


def _ids_from_landing_payload(payload: dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    metadata = payload.get("metadata") or {}
    brand_id = metadata.get("brandId")
    model_id = metadata.get("modelId")
    generation_id = metadata.get("generationId")
    initial = str(payload.get("initialValue") or "")
    qs = parse_qs(initial)
    if brand_id is None and qs.get("brand"):
        brand_id = int(qs["brand"][0])
    if model_id is None and qs.get("model"):
        model_id = int(qs["model"][0])
    if generation_id is None and qs.get("generation"):
        generation_id = int(qs["generation"][0])
    return (
        int(brand_id) if brand_id else None,
        int(model_id) if model_id else None,
        int(generation_id) if generation_id else None,
    )


def _candidate_landing_slugs(target: AvbyPriceStatTarget) -> list[str]:
    """ocenka landings often use `{catalog_slug}_{year}`."""
    base = target.catalog_slug
    years = years_for_target(target)
    year_picks: list[int] = []
    if years:
        for y in (years[len(years) // 2], years[0], years[-1]):
            if y not in year_picks:
                year_picks.append(y)
    candidates = [f"{base}_{y}" for y in year_picks]
    candidates.append(base)
    return candidates


def resolve_target(client: AvbyPriceStatsClient, target: AvbyPriceStatTarget) -> None:
    last_error: Exception | None = None
    for slug in _candidate_landing_slugs(target):
        try:
            payload = client.get_json(f"/landings/ocenka-avto/{slug}")
        except Exception as exc:
            last_error = exc
            continue
        brand_id, model_id, generation_id = _ids_from_landing_payload(payload)
        if brand_id and model_id and generation_id:
            target.brand_id = brand_id
            target.model_id = model_id
            target.generation_id = generation_id
            target.resolve_status = "ready"
            target.resolve_error = None
            target.resolved_at = datetime.utcnow()
            target.updated_at = datetime.utcnow()
            return
        last_error = RuntimeError(f"Missing IDs in landing payload for {slug}")
    raise RuntimeError(
        f"Could not resolve landing IDs for {target.catalog_slug}: {last_error}"
    )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=None)
    except ValueError:
        return None


def _money(block: dict[str, Any] | None, currency: str) -> float | None:
    if not isinstance(block, dict):
        return None
    node = block.get(currency)
    if not isinstance(node, dict):
        return None
    amount = node.get("amount")
    if amount is None:
        amount = node.get("amountFiat")
    try:
        return float(amount) if amount is not None else None
    except (TypeError, ValueError):
        return None


def years_for_target(
    target: AvbyPriceStatTarget,
    *,
    min_year: int | None = None,
    max_year: int | None = None,
) -> list[int]:
    if not target.year_from:
        return []
    y0 = int(target.year_from)
    current = datetime.utcnow().year
    if target.year_to is None:
        y1 = current
    else:
        y1 = int(target.year_to)
        # Catalog typos (e.g. 1018 instead of 2018) — treat as open-ended.
        if y1 < 1950 or y1 > current + 1:
            y1 = current
    if y1 < y0:
        return []
    if min_year is not None:
        y0 = max(y0, int(min_year))
    if max_year is not None:
        y1 = min(y1, int(max_year))
    if y1 < y0:
        return []
    return list(range(y0, y1 + 1))


def fetch_and_store_year_stat(
    db: Session,
    client: AvbyPriceStatsClient,
    target: AvbyPriceStatTarget,
    year: int,
    *,
    include_active: bool = True,
    refresh: bool = False,
) -> AvbyPriceYearStat:
    assert target.brand_id and target.model_id and target.generation_id
    existing = (
        db.query(AvbyPriceYearStat)
        .filter(
            AvbyPriceYearStat.brand_id == target.brand_id,
            AvbyPriceYearStat.model_id == target.model_id,
            AvbyPriceYearStat.generation_id == target.generation_id,
            AvbyPriceYearStat.year == year,
        )
        .first()
    )
    if existing and existing.fetch_status == "ok" and not refresh:
        return existing

    params = {
        "brand": target.brand_id,
        "model": target.model_id,
        "generation": target.generation_id,
        "year": year,
        "available_year": year,
    }
    payload = client.get_json("/offer-types/cars/price-statistics", params=params)
    active_payload: dict[str, Any] | None = None
    if include_active:
        try:
            active_payload = client.get_json(
                "/offer-types/cars/price-statistics/active-adverts",
                params=params,
            )
        except Exception as exc:
            logger.warning(
                "active-adverts failed brand=%s model=%s gen=%s year=%s: %s",
                target.brand_id,
                target.model_id,
                target.generation_id,
                year,
                exc,
            )

    title = payload.get("title") or {}
    medium = payload.get("mediumPrice") or {}
    activity = payload.get("advertActivity") or {}
    last = activity.get("last") or {}
    main_filter = medium.get("mainFilter") or {}

    row = existing or AvbyPriceYearStat(
        target_id=target.id,
        brand_id=target.brand_id,
        model_id=target.model_id,
        generation_id=target.generation_id,
        year=year,
    )
    row.make = title.get("brand") or target.make
    row.model_name = title.get("model") or target.model
    row.generation_name = title.get("generation") or target.generation
    row.image_url = title.get("image")
    row.price_usd = medium.get("priceUsd")
    row.price_byn = medium.get("priceByn")
    row.min_price_usd = medium.get("minPriceUsd")
    row.max_price_usd = medium.get("maxPriceUsd")
    row.advert_count = medium.get("advertCount")
    row.activity_new_60d = last.get("new")
    row.activity_removed_60d = last.get("removed")
    row.activity_days = activity.get("activityDays")
    row.activity_by_month = activity.get("byMonth")
    row.main_filter_url = (main_filter or {}).get("url")
    row.raw_payload = payload
    row.fetch_status = "ok"
    row.fetch_error = None
    row.fetched_at = datetime.utcnow()
    if active_payload:
        row.active_advert_count = active_payload.get("advertCount")
        row.active_filter_url = ((active_payload.get("mainFilter") or {}) or {}).get("url")
        row.active_payload = active_payload
    if existing is None:
        db.add(row)
    db.flush()

    db.query(AvbyPriceHistoryPoint).filter(AvbyPriceHistoryPoint.year_stat_id == row.id).delete()
    for point in payload.get("history") or []:
        db.add(
            AvbyPriceHistoryPoint(
                year_stat_id=row.id,
                year=int(point.get("year") or 0),
                month=int(point.get("month") or 0),
                median_price_usd=point.get("medianPriceUsd"),
            )
        )

    db.query(AvbyPriceSoldAdvert).filter(AvbyPriceSoldAdvert.year_stat_id == row.id).delete()
    for advert in payload.get("lastSoldAdverts") or []:
        avby_id = advert.get("id")
        if not avby_id:
            continue
        price = advert.get("price") or {}
        status = advert.get("publicStatus") or {}
        db.add(
            AvbyPriceSoldAdvert(
                year_stat_id=row.id,
                avby_id=int(avby_id),
                price_usd=_money(price, "usd"),
                price_byn=_money(price, "byn"),
                days_on_sale=advert.get("originalDaysOnSale"),
                published_at=_parse_dt(advert.get("publishedAt")),
                public_status=(status.get("name") if isinstance(status, dict) else None),
                payload=advert,
            )
        )
    db.commit()
    db.refresh(row)
    return row
