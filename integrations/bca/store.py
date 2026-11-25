"""SQLite storage for one BCA sale, its lots, and downloaded documents."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS bca_auctions (
    id INTEGER PRIMARY KEY,
    sale_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL DEFAULT '',
    country TEXT NOT NULL DEFAULT '',
    sale_type TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    starts_at TEXT,
    catalogue_url TEXT NOT NULL DEFAULT '',
    section_url TEXT NOT NULL DEFAULT '',
    lot_count INTEGER NOT NULL DEFAULT 0,
    can_view_pricing INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bca_lots (
    id INTEGER PRIMARY KEY,
    auction_id INTEGER NOT NULL REFERENCES bca_auctions(id) ON DELETE CASCADE,
    vehicle_id TEXT NOT NULL UNIQUE,
    lot_id TEXT NOT NULL DEFAULT '',
    lot_number TEXT NOT NULL DEFAULT '',
    lot_url TEXT NOT NULL DEFAULT '',
    headline TEXT NOT NULL DEFAULT '',
    make TEXT NOT NULL DEFAULT '',
    model TEXT NOT NULL DEFAULT '',
    derivative TEXT NOT NULL DEFAULT '',
    vin TEXT NOT NULL DEFAULT '',
    mileage_km INTEGER,
    registration TEXT NOT NULL DEFAULT '',
    registration_date TEXT NOT NULL DEFAULT '',
    fuel_type TEXT NOT NULL DEFAULT '',
    power_kw INTEGER,
    power_ps INTEGER,
    sale_location TEXT NOT NULL DEFAULT '',
    vehicle_location TEXT NOT NULL DEFAULT '',
    image_url TEXT NOT NULL DEFAULT '',
    bid_now TEXT NOT NULL DEFAULT '',
    buy_now TEXT NOT NULL DEFAULT '',
    condition_report_url TEXT NOT NULL DEFAULT '',
    mechanical_report_url TEXT NOT NULL DEFAULT '',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bca_documents (
    id INTEGER PRIMARY KEY,
    auction_id INTEGER REFERENCES bca_auctions(id) ON DELETE CASCADE,
    lot_pk INTEGER REFERENCES bca_lots(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT '',
    byte_size INTEGER,
    storage_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL,
    UNIQUE (kind, source_url)
);

CREATE INDEX IF NOT EXISTS ix_bca_lots_auction_id ON bca_lots(auction_id);
CREATE INDEX IF NOT EXISTS ix_bca_lots_vin ON bca_lots(vin);
CREATE INDEX IF NOT EXISTS ix_bca_documents_auction_id ON bca_documents(auction_id);
CREATE INDEX IF NOT EXISTS ix_bca_documents_lot_pk ON bca_documents(lot_pk);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA)
    return connection


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def upsert_auction(connection: sqlite3.Connection, auction: dict[str, Any], *, seen_at: datetime) -> int:
    now = _iso(seen_at)
    connection.execute(
        """
        INSERT INTO bca_auctions (
            sale_id, name, country, sale_type, channel, location, starts_at,
            catalogue_url, section_url, lot_count, can_view_pricing,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(sale_id) DO UPDATE SET
            name=excluded.name,
            country=excluded.country,
            sale_type=excluded.sale_type,
            channel=excluded.channel,
            location=excluded.location,
            starts_at=excluded.starts_at,
            catalogue_url=excluded.catalogue_url,
            section_url=excluded.section_url,
            lot_count=excluded.lot_count,
            can_view_pricing=excluded.can_view_pricing,
            last_seen_at=excluded.last_seen_at
        """,
        (
            auction["sale_id"],
            auction["name"],
            auction["country"],
            auction["sale_type"],
            auction["channel"],
            auction["location"],
            _iso(auction["starts_at"]),
            auction["catalogue_url"],
            auction["section_url"],
            auction["lot_count"],
            1 if auction["can_view_pricing"] else 0,
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT id FROM bca_auctions WHERE sale_id = ?",
        (auction["sale_id"],),
    ).fetchone()
    return int(row["id"])


def upsert_lot(
    connection: sqlite3.Connection,
    auction_id: int,
    lot: dict[str, Any],
    *,
    seen_at: datetime,
) -> int:
    now = _iso(seen_at)
    connection.execute(
        """
        INSERT INTO bca_lots (
            auction_id, vehicle_id, lot_id, lot_number, lot_url, headline,
            make, model, derivative, vin, mileage_km, registration,
            registration_date, fuel_type, power_kw, power_ps, sale_location,
            vehicle_location, image_url, bid_now, buy_now,
            condition_report_url, mechanical_report_url,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(vehicle_id) DO UPDATE SET
            auction_id=excluded.auction_id,
            lot_id=excluded.lot_id,
            lot_number=excluded.lot_number,
            lot_url=excluded.lot_url,
            headline=excluded.headline,
            make=excluded.make,
            model=excluded.model,
            derivative=excluded.derivative,
            vin=excluded.vin,
            mileage_km=excluded.mileage_km,
            registration=excluded.registration,
            registration_date=excluded.registration_date,
            fuel_type=excluded.fuel_type,
            power_kw=excluded.power_kw,
            power_ps=excluded.power_ps,
            sale_location=excluded.sale_location,
            vehicle_location=excluded.vehicle_location,
            image_url=excluded.image_url,
            bid_now=excluded.bid_now,
            buy_now=excluded.buy_now,
            condition_report_url=excluded.condition_report_url,
            mechanical_report_url=excluded.mechanical_report_url,
            last_seen_at=excluded.last_seen_at
        """,
        (
            auction_id,
            lot["vehicle_id"],
            lot["lot_id"],
            lot["lot_number"],
            lot["lot_url"],
            lot["headline"],
            lot["make"],
            lot["model"],
            lot["derivative"],
            lot["vin"],
            lot["mileage_km"],
            lot["registration"],
            lot["registration_date"],
            lot["fuel_type"],
            lot["power_kw"],
            lot["power_ps"],
            lot["sale_location"],
            lot["vehicle_location"],
            lot["image_url"],
            lot["bid_now"],
            lot["buy_now"],
            lot["condition_report_url"],
            lot["mechanical_report_url"],
            now,
            now,
        ),
    )
    row = connection.execute(
        "SELECT id FROM bca_lots WHERE vehicle_id = ?",
        (lot["vehicle_id"],),
    ).fetchone()
    return int(row["id"])


def upsert_document(
    connection: sqlite3.Connection,
    *,
    auction_id: int,
    lot_pk: int | None,
    kind: str,
    source_url: str,
    content_type: str,
    byte_size: int | None,
    storage_path: str,
    status: str,
    detail: str,
    fetched_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO bca_documents (
            auction_id, lot_pk, kind, source_url, content_type, byte_size,
            storage_path, status, detail, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(kind, source_url) DO UPDATE SET
            auction_id=excluded.auction_id,
            lot_pk=excluded.lot_pk,
            content_type=excluded.content_type,
            byte_size=excluded.byte_size,
            storage_path=excluded.storage_path,
            status=excluded.status,
            detail=excluded.detail,
            fetched_at=excluded.fetched_at
        """,
        (
            auction_id,
            lot_pk,
            kind,
            source_url,
            content_type,
            byte_size,
            storage_path,
            status,
            detail,
            _iso(fetched_at),
        ),
    )
