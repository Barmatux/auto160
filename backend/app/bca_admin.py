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


def media_download_url(key: str) -> str:
    """Attachment URL for a file already stored in our bucket."""
    value = (key or "").strip()
    if not value or ".." in value or value.startswith("/"):
        return ""
    return f"/media/object?key={quote(value, safe='')}&download=1"


def _with_download(url: str) -> str:
    key = storage_key_from_media_url(url)
    return media_download_url(key) if key else ""


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
        rows.append(_lot_row(lot, auction))
    auction_ids = {auction.id for _, auction in pairs}
    return {
        "rows": rows,
        "total": len(rows),
        "auction_count": len(auction_ids),
        "countries": countries,
        "lot_total": sum(item["count"] for item in countries),
    }


def auction_lot_view(db, lot_id: int) -> dict | None:
    from app.models import BcaAuction, BcaLot

    pair = (
        db.query(BcaLot, BcaAuction)
        .join(BcaAuction, BcaLot.auction_id == BcaAuction.id)
        .filter(BcaLot.id == lot_id)
        .one_or_none()
    )
    if pair is None:
        return None
    lot, auction = pair
    row = _lot_row(lot, auction)
    row["registration"] = lot.registration or ""
    row["specs"] = [
        item
        for item in (
            ("Год", row["year"] if row["year"] != "—" else ""),
            ("Пробег", _mileage_text(row["mileage"])),
            ("Топливо", row["fuel"] if row["fuel"] != "—" else ""),
            ("VIN", row["vin"]),
            ("Рег. номер", row["registration"]),
            ("Страна", row["country"] if row["country"] != "—" else ""),
            ("Аукцион", row["auction_name"] if row["auction_name"] != "—" else ""),
            ("Где стоит", row["city"] if row["city"] != "—" else ""),
        )
        if item[1]
    ]
    return row


def _mileage_text(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}".replace(",", " ") + " км"


def _lot_row(lot, auction) -> dict:
    download_url = _with_download(lot.condition_report_url or "")
    return {
        "id": lot.id,
        "headline": lot.headline or "—",
        "year": lot.registration_date if str(lot.registration_date or "").isdigit() else _year(lot.headline),
        "mileage": lot.mileage_km,
        "fuel": fuel_label(lot.fuel_type) or "—",
        "city": lot.vehicle_location or "—",
        "country": country_label(auction.country),
        "country_code": auction.country or "",
        "auction_name": auction.name or "—",
        "photo_url": lot.image_url or "",
        "photos": [url for url in (lot.photo_urls or []) if url] or ([lot.image_url] if lot.image_url else []),
        "lot_url": lot.lot_url or "",
        "download_url": download_url,
        "vin": lot.vin or "",
    }


def _year(headline: str) -> str:
    tail = (headline or "").rsplit(",", 1)
    if len(tail) == 2 and tail[1].strip().isdigit() and len(tail[1].strip()) == 4:
        return tail[1].strip()
    return "—"


def _store_inspection_document(db, lot, auction, inspection: str) -> None:
    if not inspection or ".." in inspection or inspection.startswith("/"):
        return
    from app.models import BcaDocument

    document = (
        db.query(BcaDocument)
        .filter(BcaDocument.kind == "inspection", BcaDocument.source_url == inspection)
        .one_or_none()
    )
    if document is None:
        document = BcaDocument(kind="inspection", source_url=inspection, fetched_at=lot.last_seen_at)
        db.add(document)
    document.auction_id = auction.id
    document.lot_pk = lot.id
    document.content_type = "application/pdf"
    document.storage_path = inspection
    document.status = "stored"
    document.detail = ""


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
        lot.lot_id = str(item.get("lot_id") or "")[:32]
        lot.vin = str(item.get("vin") or "")[:32]
        lot.registration = str(item.get("registration") or "")[:32]
        lot.mileage_km = corrected_mileage(item.get("mileage_km"))
        lot.fuel_type = str(item.get("fuel") or "")[:40]
        lot.registration_date = str(item.get("year") or "")[:40]
        lot.vehicle_location = str(item.get("city") or "")[:160]
        gallery = [
            str(url)
            for url in (item.get("photo_urls") or [])
            if str(url).startswith("/media/object?key=")
        ]
        if gallery:
            lot.photo_urls = gallery[:12]
            lot.image_url = gallery[0]
        else:
            lot.image_url = str(item.get("photo_url") or "")
        lot.photo_s3_key = storage_key_from_media_url(lot.image_url)
        inspection = str(item.get("inspection_key") or "").strip()
        lot.condition_report_url = (
            f"/media/object?key={quote(inspection, safe='')}" if inspection else ""
        )
        lot.last_seen_at = now
        db.flush()
        _store_inspection_document(db, lot, auction, inspection)
        saved += 1
    db.flush()
    for auction in auctions.values():
        auction.lot_count = db.query(BcaLot).filter(BcaLot.auction_id == auction.id).count()
    return saved


# A short or empty push must not wipe the public catalog.
REPLACE_MIN_LOTS = 50


def sync_parsed_lots(db, items: list[dict], *, replace: bool = False) -> dict:
    """Upsert the parser snapshot. A full snapshot also drops lots that left the catalog."""
    saved = upsert_parsed_lots(db, items)
    removed = 0
    if replace and saved >= REPLACE_MIN_LOTS:
        removed = _drop_lots_outside(db, items)
    return {"saved": saved, "removed": removed}


def _drop_lots_outside(db, items: list[dict]) -> int:
    from sqlalchemy import func

    from app.models import BcaAuction, BcaDocument, BcaLot

    keep = {str(item.get("vehicle_id") or "").strip() for item in items}
    keep.discard("")
    stale_ids = [
        row[0]
        for row in db.query(BcaLot.id).filter(BcaLot.vehicle_id.notin_(keep)).all()
    ]
    removed = 0
    if stale_ids:
        db.query(BcaDocument).filter(BcaDocument.lot_pk.in_(stale_ids)).delete(synchronize_session=False)
        removed = db.query(BcaLot).filter(BcaLot.id.in_(stale_ids)).delete(synchronize_session=False)
        db.flush()
    empty_ids = [
        row[0]
        for row in (
            db.query(BcaAuction.id)
            .outerjoin(BcaLot, BcaLot.auction_id == BcaAuction.id)
            .group_by(BcaAuction.id)
            .having(func.count(BcaLot.id) == 0)
            .all()
        )
    ]
    if empty_ids:
        db.query(BcaDocument).filter(BcaDocument.auction_id.in_(empty_ids)).delete(synchronize_session=False)
        db.query(BcaAuction).filter(BcaAuction.id.in_(empty_ids)).delete(synchronize_session=False)
        db.flush()
    for auction in db.query(BcaAuction).all():
        auction.lot_count = db.query(BcaLot).filter(BcaLot.auction_id == auction.id).count()
    return int(removed or 0)
