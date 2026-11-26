"""Admin view of parsed BCA auction lots."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import parse_qs, quote, unquote, urlparse

COUNTRY_LABELS = {
    "DE": "Германия",
    "DK": "Дания",
    "FR": "Франция",
    "EU": "Европа",
}


def country_label(code: str) -> str:
    value = (code or "").strip().upper()
    if not value:
        return "—"
    name = COUNTRY_LABELS.get(value)
    return f"{name} ({value})" if name else value


def fuel_label(value: str) -> str:
    text = (value or "").strip()
    low = text.lower()
    if low.startswith("bev") or "electric" in low:
        return "Электро"
    if "phev" in low or "plug" in low or low.startswith("hev"):
        return "Гибрид"
    if low.startswith("diesel"):
        return "Дизель"
    if low.startswith("petrol") or low.startswith("benz"):
        return "Бензин"
    return text[:40]


def corrected_mileage(value: int | None) -> int | None:
    """BCA sometimes sends kilometres with a trailing decimal zero."""
    if value is None:
        return None
    if value >= 10_000 and value % 10 == 0:
        return value // 10
    return value


def storage_key_from_media_url(url: str) -> str:
    if not url:
        return ""
    key = parse_qs(urlparse(url).query).get("key", [""])[0]
    return unquote(key)


def auction_admin_view(db, *, country: str = "", q: str = "") -> dict:
    from sqlalchemy import func, or_

    from app.models import BcaAuction, BcaLot
    country_code = (country or "").strip().upper()
    query_text = (q or "").strip()
    counts = (
        db.query(BcaAuction.country, func.count(BcaLot.id))
        .join(BcaLot, BcaLot.auction_id == BcaAuction.id)
        .group_by(BcaAuction.country)
        .order_by(BcaAuction.country)
        .all()
    )
    countries = [
        {"code": code or "", "label": country_label(code or ""), "count": count}
        for code, count in counts
    ]
    lots_query = db.query(BcaLot, BcaAuction).join(BcaAuction, BcaLot.auction_id == BcaAuction.id)
    if country_code:
        lots_query = lots_query.filter(BcaAuction.country == country_code)
    if query_text:
        like = f"%{query_text}%"
        lots_query = lots_query.filter(
            or_(
                BcaLot.headline.ilike(like),
                BcaAuction.name.ilike(like),
                BcaLot.vin.ilike(like),
                BcaLot.vehicle_location.ilike(like),
            )
        )
    pairs = lots_query.order_by(BcaAuction.country, BcaAuction.name, BcaLot.headline, BcaLot.id).all()
    rows = []
    for lot, auction in pairs:
        rows.append(
            {
                "headline": lot.headline or "—",
                "year": lot.registration_date if str(lot.registration_date or "").isdigit() else _year(lot.headline),
                "mileage": lot.mileage_km,
                "fuel": fuel_label(lot.fuel_type),
                "city": lot.vehicle_location or "—",
                "country": country_label(auction.country),
                "country_code": auction.country or "",
                "auction_name": auction.name or "—",
                "photo_url": lot.image_url or "",
                "lot_url": lot.lot_url or "",
                "report_url": lot.condition_report_url or "",
                "vin": lot.vin or "",
            }
        )
    auction_ids = {auction.id for _, auction in pairs}
    return {
        "rows": rows,
        "total": len(rows),
        "auction_count": len(auction_ids),
        "countries": countries,
        "lot_total": sum(item["count"] for item in countries),
    }


def _year(headline: str) -> str:
    tail = (headline or "").rsplit(",", 1)
    if len(tail) == 2 and tail[1].strip().isdigit() and len(tail[1].strip()) == 4:
        return tail[1].strip()
    return "—"


def upsert_parsed_lots(db, items: list[dict]) -> int:
    from app.models import BcaAuction, BcaLot
    now = datetime.utcnow()
    auctions: dict[str, BcaAuction] = {}
    saved = 0
    for item in items:
        vehicle_id = str(item.get("vehicle_id") or "").strip()
        if not vehicle_id:
            continue
        sale_id = str(item.get("sale_id") or "").strip()
        if not sale_id:
            sale_id = f"{item.get('country') or ''}:{item.get('auction_name') or ''}"[:64]
        auction = auctions.get(sale_id)
        if auction is None:
            auction = db.query(BcaAuction).filter(BcaAuction.sale_id == sale_id).one_or_none()
            if auction is None:
                auction = BcaAuction(sale_id=sale_id[:64], first_seen_at=now)
                db.add(auction)
            auction.name = str(item.get("auction_name") or auction.name or "")[:300]
            auction.country = str(item.get("country") or "")[:8]
            auction.last_seen_at = now
            db.flush()
            auctions[sale_id] = auction
        lot = db.query(BcaLot).filter(BcaLot.vehicle_id == vehicle_id).one_or_none()
        if lot is None:
            lot = BcaLot(vehicle_id=vehicle_id[:64], auction_id=auction.id, first_seen_at=now)
            db.add(lot)
        title = str(item.get("title") or "")
        lot.auction_id = auction.id
        lot.headline = title
        lot.make = (title.split(" ", 1)[0] if title else "")[:80]
        lot.lot_url = str(item.get("url") or "")
        lot.vin = str(item.get("vin") or "")[:32]
        lot.mileage_km = corrected_mileage(item.get("mileage_km"))
        lot.fuel_type = str(item.get("fuel") or "")[:40]
        lot.registration_date = str(item.get("year") or "")[:40]
        lot.vehicle_location = str(item.get("city") or "")[:160]
        lot.image_url = str(item.get("photo_url") or "")
        lot.photo_s3_key = storage_key_from_media_url(lot.image_url)
        inspection = str(item.get("inspection_key") or "").strip()
        lot.condition_report_url = (
            f"/media/object?key={quote(inspection, safe='')}" if inspection else ""
        )
        lot.last_seen_at = now
        saved += 1
    db.flush()
    for auction in auctions.values():
        auction.lot_count = db.query(BcaLot).filter(BcaLot.auction_id == auction.id).count()
    return saved
